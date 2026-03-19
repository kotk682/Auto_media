from openai import AsyncOpenAI
from app.services.store import save_story, get_story
from app.services.mock_service import (
    mock_analyze_idea, mock_generate_outline, mock_generate_script, mock_chat
)

MODEL_MAP = {
    "qwen": "qwen-plus",
    "openai": "gpt-4o-mini",
    "zhipu": "glm-4-flash",
    "gemini": "gemini-2.0-flash",
    "claude": "claude-sonnet-4-6",
}

ANALYZE_PROMPT = """你是一位资深短剧编剧，擅长快节奏、高冲突、钩子密集的剧本创作。最终剧本将用于 AI 视频生成，请优先考虑视觉冲击力强、场景具象的设定。

用户原始灵感：{idea}
风格类型：{genre}
故事基调：{tone}

请对这个灵感进行【要素审计】：
1. 世界观是否清晰？
2. 主角动机是否强烈？
3. 核心冲突是否有视觉表现力？（优先具象超能力/场景，避免抽象设定）

以 JSON 格式返回，结构如下：
{{
  "analysis": "简短分析（1-2句，指出最大的缺失要素）",
  "suggestions": [
    {{
      "label": "追问维度名称",
      "options": ["选项A", "选项B", "选项C"]
    }}
  ],
  "placeholder": "引导用户自由输入的提示语"
}}

只返回 JSON，不要其他内容。"""

OUTLINE_PROMPT = """你是一位资深短剧编剧，擅长快节奏、高冲突、钩子密集的剧本创作。最终剧本将用于 AI 视频生成，请优先考虑视觉冲击力强、场景具象的设定。

故事设定：{selected_setting}

请以JSON格式返回完整大纲，结构如下：
{{
  "meta": {{"title": "故事标题", "genre": "类型", "episodes": 6, "theme": "主题"}},
  "characters": [
    {{"name": "角色名", "role": "主角/配角", "description": "角色描述"}}
  ],
  "relationships": [
    {{"source": "角色A", "target": "角色B", "label": "关系描述"}}
  ],
  "outline": [
    {{"episode": 1, "title": "集标题", "summary": "剧情概要，包含具体场景和冲突"}}
  ]
}}

只返回JSON，不要其他内容。"""

SCRIPT_PROMPT = """你是一位资深短剧导演兼编剧。根据以下大纲，为第{episode}集「{title}」写导演分镜剧本。

剧情概要：{summary}

输出要求（用于后续 AI 视频生成）：
- 【环境】和【画面】将直接送入图像生成 API，必须具象、可视化，避免抽象描述
- 【台词/旁白】将直接送入 TTS 语音 API，画面与声音严格分离
- 每集 3-5 个场景

请以JSON格式返回，结构如下：
{{
  "episode": {episode},
  "title": "{title}",
  "scenes": [
    {{
      "scene_number": 1,
      "environment": "时间、地点、天气、光线等环境描述，具象细节",
      "visual": "画面内容：人物位置、动作、表情、镜头角度等，不含对话",
      "audio": [
        {{"character": "角色名或旁白", "line": "台词或旁白内容"}}
      ]
    }}
  ]
}}

只返回JSON，不要其他内容。"""

REFINE_PROMPT = """你是一位资深短剧编剧。用户对故事内容进行了修改，请根据修改内容判断哪些模块需要更新，并返回更新后的内容。

当前故事完整信息：
{story_json}

用户的修改：
类型：{change_type}
内容：{change_summary}

请判断以下模块是否需要因此次修改而更新：
1. 人物关系（relationships）：如果角色描述变化影响了人物之间的关系
2. 剧情大纲（outline）：如果修改影响了其他集的剧情走向
3. 故事主题（meta.theme）：如果整体主题发生了变化

只更新确实需要变化的模块，不需要变化的返回 null。

以 JSON 格式返回：
{{
  "relationships": null 或 [{{"source": "角色A", "target": "角色B", "label": "关系"}}],
  "outline": null 或 [{{"episode": 1, "title": "标题", "summary": "概要"}}],
  "meta_theme": null 或 "新的主题描述"
}}

只返回 JSON，不要其他内容。"""


def _make_client(api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url or None)


def _get_model(provider: str) -> str:
    return MODEL_MAP.get(provider, "qwen-plus")


def _parse_json(content: str):
    import json as _json
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else parts[0]
        if content.startswith("json"):
            content = content[4:]
    return _json.loads(content.strip())


async def refine(story_id: str, change_type: str, change_summary: str, api_key: str = "", base_url: str = "", provider: str = "") -> dict:
    import json as _json
    story = get_story(story_id)
    if not api_key:
        return {"relationships": None, "outline": None, "meta_theme": None}

    client = _make_client(api_key, base_url)
    prompt = REFINE_PROMPT.format(
        story_json=_json.dumps(story, ensure_ascii=False),
        change_type=change_type,
        change_summary=change_summary,
    )
    resp = await client.chat.completions.create(
        model=_get_model(provider),
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        data = _parse_json(resp.choices[0].message.content)
    except Exception:
        return {"relationships": None, "outline": None, "meta_theme": None}
    usage = resp.usage
    return {
        "relationships": data.get("relationships"),
        "outline": data.get("outline"),
        "meta_theme": data.get("meta_theme"),
        "usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None,
    }


async def analyze_idea(idea: str, genre: str, tone: str, api_key: str = "", base_url: str = "", provider: str = "") -> dict:
    if not api_key:
        return await mock_analyze_idea(idea, genre, tone)

    import json as _json
    import uuid
    client = _make_client(api_key, base_url)
    prompt = ANALYZE_PROMPT.format(idea=idea, genre=genre, tone=tone)
    resp = await client.chat.completions.create(
        model=_get_model(provider),
        messages=[{"role": "user", "content": prompt}],
    )
    data = _parse_json(resp.choices[0].message.content)
    story_id = str(uuid.uuid4())
    save_story(story_id, {"idea": idea, "genre": genre, "tone": tone})
    usage = resp.usage
    return {
        "story_id": story_id,
        "analysis": data.get("analysis", ""),
        "suggestions": data.get("suggestions", []),
        "placeholder": data.get("placeholder", ""),
        "usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None,
    }


async def generate_outline(story_id: str, selected_setting: str, api_key: str = "", base_url: str = "", provider: str = "") -> dict:
    if not api_key:
        return await mock_generate_outline(story_id, selected_setting)

    client = _make_client(api_key, base_url)
    prompt = OUTLINE_PROMPT.format(selected_setting=selected_setting)
    resp = await client.chat.completions.create(
        model=_get_model(provider),
        messages=[{"role": "user", "content": prompt}],
    )
    data = _parse_json(resp.choices[0].message.content)
    save_story(story_id, {"selected_setting": selected_setting, "outline": data.get("outline", [])})
    usage = resp.usage
    return {
        "story_id": story_id,
        **data,
        "usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None,
    }


async def chat(story_id: str, message: str, api_key: str = "", base_url: str = "", provider: str = ""):
    if not api_key:
        async for chunk in mock_chat(story_id, message):
            yield chunk
        return

    client = _make_client(api_key, base_url)
    stream = await client.chat.completions.create(
        model=_get_model(provider),
        messages=[{"role": "user", "content": message}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def generate_script(story_id: str, api_key: str = "", base_url: str = "", provider: str = ""):
    if not api_key:
        async for scene in mock_generate_script(story_id):
            yield scene
        return

    story = get_story(story_id)
    outline = story.get("outline", [])
    if not outline:
        async for scene in mock_generate_script(story_id):
            yield scene
        return
    client = _make_client(api_key, base_url)

    total_prompt = 0
    total_completion = 0
    for ep in outline:
        prompt = SCRIPT_PROMPT.format(
            episode=ep["episode"],
            title=ep["title"],
            summary=ep["summary"],
        )
        resp = await client.chat.completions.create(
            model=_get_model(provider),
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.usage:
            total_prompt += resp.usage.prompt_tokens
            total_completion += resp.usage.completion_tokens
        try:
            yield _parse_json(resp.choices[0].message.content)
        except Exception:
            yield {"episode": ep["episode"], "title": ep["title"], "scenes": []}

    yield {"__usage__": {"prompt_tokens": total_prompt, "completion_tokens": total_completion}}
