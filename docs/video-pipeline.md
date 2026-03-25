# Auto_media 视频生成管线文档

> 后端处理逻辑：从分镜 JSON 到视频成片的质量控制链路
> 提示词模板详见 [prompt-framework.md](prompt-framework.md)
> 更新日期：2026-03-25

---

## 一、管线总览

> 说明：本文中较早出现的 `build_final_prompt()` 属于设计期命名。按照当前仓库实现，更接近真实代码边界的入口是 `app/core/story_context.py` 中的 `build_generation_payload()`，由 `PipelineExecutor`、`image.py`、`video.py` 等链路复用。

```text
分镜 JSON (Shot List)
  │
  ├─ 0. StoryContext 构建 ─── 角色锁、画风、场景风格、negative prompt 汇总
  ├─ 1. CharacterLock 注入 ── 角色外貌/服装锚点合并到生成 payload
  ├─ 2. 镜头流上下文注入 ─── 携带前一镜头环境信息，添加衔接短语
  ├─ 3. 强度分级渲染标签 ─── 按 scene_intensity 注入 low/high 渲染参数
  ├─ 4. Negative Prompt ──── 通过独立字段或 provider 参数注入
  │
  ▼
  build_generation_payload() / build_*_generation_prompt()
  │
  ├─ 5. Judge Agent 审查 ─── fast model 逻辑/物理一致性检查（可选）
  ├─ 6. 起始帧生成 ────── 静态图作为视频首帧引导（可选，视 API 支持）
  ├─ 7. VLM 反馈闭环 ──── 关键镜头抽检，不通过则增强 prompt 后有限次重试（规划中）
  │
  ▼
  视频生成 API (Kling / Runway / Seedance / Sora)
  │
  ├─ 8. 换脸后处理 ────── 替代/增强角色一致性（可选，视 API 支持）
  │
  ▼
  最终视频素材
```

---

## 二、Visual DNA 注入

### 问题

LLM 每次生成分镜时自由描述角色外貌 → 同一角色跨镜头不一致（发型变、服装扣子变、甚至性别变）。

### 方案

在 `build_final_prompt()` 中，将 `visual_elements.subject_and_clothing` 强制替换为该角色在 `character_images` 中存储的 `visual_dna` 固定串。

```python
def inject_visual_dna(shot: dict, character_dna: dict[str, str]) -> dict:
    """
    将 shot 中的 subject_and_clothing 替换为固定 Visual DNA。

    Args:
        shot: 单个 Shot 字典
        character_dna: {角色名: visual_dna_string}
    """
    subject = shot["visual_elements"]["subject_and_clothing"]

    for name, dna in character_dna.items():
        # 如果 subject 中提到了该角色（英文名或中文名），替换为固定 DNA
        if name.lower() in subject.lower() or name in subject:
            # 保留 LLM 生成的动态部分（如局部特写描述），在前面插入固定 DNA
            shot["visual_elements"]["subject_and_clothing"] = dna
            break

    return shot
```

### Visual DNA 生成时机

在 Step 2.5（角色参考图生成后），有两种方式提取 Visual DNA：

**方式 A（推荐）**：用 LLM 从角色描述中提炼固定英文短语

```python
VISUAL_DNA_PROMPT = """从以下角色描述中，提取一段固定的英文外貌描述（30-50词），
严格遵循格式：年龄+种族+性别, 发型+发色, 显著特征, 服装材质+颜色+类型+细节, 体型

角色名：{name}
角色描述：{description}

只返回英文描述串，不要其他内容。"""
```

**方式 B**：人工编写后存入 `character_images[name]["visual_dna"]`

---

## 三、镜头流上下文注入

### 问题

视频模型只看当前 Prompt → 相邻镜头的背景、光影突然变色（跳戏）。

### 方案

在 `build_final_prompt()` 中，将前一镜头的环境和光影信息作为衔接上下文追加。

```python
def inject_temporal_context(current_shot: dict, prev_shot: dict | None) -> dict:
    """
    向 final_video_prompt 注入前一镜头的环境/光影上下文。
    仅在同一场景内（scene_number 相同）注入。
    """
    if prev_shot is None:
        return current_shot

    # 仅同场景内注入（跨场景不需要衔接）
    curr_scene = current_shot["shot_id"].split("_")[0]  # "scene1"
    prev_scene = prev_shot["shot_id"].split("_")[0]
    if curr_scene != prev_scene:
        return current_shot

    prev_env = prev_shot["visual_elements"]["environment_and_props"]
    prev_light = prev_shot["visual_elements"]["lighting_and_color"]

    continuity = f"Maintaining consistent environment: {prev_env}. Continuing lighting: {prev_light}."

    current_shot["final_video_prompt"] = (
        current_shot["final_video_prompt"].rstrip(". ")
        + f". {continuity}"
    )

    return current_shot
```

---

## 四、强度分级渲染标签

根据 `scene_intensity` 注入不同级别的渲染后缀和额外参数。

```python
RENDER_PROFILES = {
    "low": {
        "tags": "Cinematic, 4k resolution, photorealistic, --ar 16:9",
        "extra": "natural lighting, steady camera, realistic movement",
    },
    "high": {
        "tags": "Masterpiece, 8k resolution, highly detailed, photorealistic, shot on ARRI Alexa 65 macro lens, --ar 16:9",
        "extra": "macro details, slow motion 120fps, volumetric lighting, subsurface scattering",
    },
}

def apply_intensity_profile(shot: dict) -> dict:
    """根据 scene_intensity 替换 final_video_prompt 末尾的渲染标签。"""
    intensity = shot.get("scene_intensity", "low")
    profile = RENDER_PROFILES.get(intensity, RENDER_PROFILES["low"])

    prompt = shot["final_video_prompt"]

    # 移除 LLM 生成的默认渲染标签（如果有），追加分级标签
    # 简单策略：在最后一个句号后替换
    if profile["extra"]:
        prompt = f"{prompt}, {profile['extra']}"

    shot["final_video_prompt"] = prompt
    return shot
```

---

## 五、Negative Prompt 注入

视频生成经常出现崩坏肢体和诡异闪烁。在 `final_video_prompt` 末尾追加画质约束。

```python
NEGATIVE_SUFFIX = (
    " --negative low quality, blurry, distorted limbs, extra fingers, "
    "messy anatomy, flickering, morphing, low resolution, watermark, text overlay"
)

def inject_negative_prompt(shot: dict) -> dict:
    """追加 Negative Prompt 后缀（部分模型支持 --negative 语法）。"""
    shot["final_video_prompt"] += NEGATIVE_SUFFIX
    return shot
```

> 注意：并非所有视频 API 都支持 `--negative` 语法。如 API 提供独立的 `negative_prompt` 参数，应改为在 API 调用层传入，而非拼接到 prompt 字符串中。

---

## 六、build_final_prompt 组装（完整流程）

> 当前代码中已经拆分为 `build_image_generation_prompt()` / `build_video_generation_prompt()` / `build_last_frame_generation_prompt()` 与 `build_generation_payload()`；本节保留的是设计上的等价表达。

将以上所有步骤串联为统一的后处理函数：

```python
def build_final_prompt(
    shots: list[dict],
    character_dna: dict[str, str],
    enable_negative: bool = True,
) -> list[dict]:
    """
    对分镜 JSON 执行完整的后处理管线。

    Args:
        shots: LLM 生成的原始 Shot 列表
        character_dna: {角色名: visual_dna_string}
        enable_negative: 是否追加 Negative Prompt
    """
    prev_shot = None

    for shot in shots:
        # 1. Visual DNA 注入
        inject_visual_dna(shot, character_dna)

        # 2. 镜头流上下文
        inject_temporal_context(shot, prev_shot)

        # 3. 强度分级
        apply_intensity_profile(shot)

        # 4. Negative Prompt
        if enable_negative:
            inject_negative_prompt(shot)

        prev_shot = shot

    return shots
```

---

## 七、Judge Agent — 分镜审查（可选）

在生成视频前，用 fast/cheap model 检查分镜逻辑和物理一致性，拦截明显错误，避免浪费昂贵的视频生成费用。

### Judge Prompt

```
你是一位专业的分镜审查员。请检查以下分镜序列中的逻辑和物理错误。

检查项：
1. 逻辑连贯：角色上一镜头倒地，下一镜头不应在奔跑（除非有起身动作）
2. 光影一致：同场景相邻镜头的光源方向和色温不应突变
3. 角色一致：同一角色的服装/发型跨镜头不应变化
4. 物理合理：不应同时出现矛盾的环境描述（如"阳光直射"和"霓虹灯映射"在同一室内场景）
5. 动作可行：单个 3-5 秒镜头中的动作是否过于复杂

分镜序列（JSON）：
{shots_json}

请以 JSON 返回：
{
  "passed": true/false,
  "issues": [
    {
      "shot_id": "scene1_shot3",
      "type": "逻辑/光影/角色/物理/动作",
      "description": "问题描述",
      "suggestion": "修正建议"
    }
  ]
}

如果没有问题，返回 {"passed": true, "issues": []}。
```

### 推荐模型

| 模型 | 速度 | 成本 | 适合场景 |
|------|------|------|---------|
| GPT-4o-mini | 快 | 极低 | 日常审查 |
| Gemini Flash | 快 | 极低 | 日常审查 |
| Claude Haiku | 快 | 低 | 需要更高准确度时 |

### 调用时机

```
storyboard.SYSTEM_PROMPT 生成 Shot List
    ↓
Judge Agent 审查
    ├─ passed=true → 进入 build_final_prompt()
    └─ passed=false → 将 issues 反馈给分镜 LLM 重新生成（最多重试 1 次）
```

---

## 八、起始帧策略（可选）

### 问题

视频模型处理复杂动作时容易出现幻觉（六指、肢体变形）。

### 方案

对每个 Shot，先用图像生成 API 生成一张高质量静态图作为视频首帧（First Frame），再用 image-to-video API 生成视频。静态图可以"锚定"角色外貌和场景布局，降低视频模型的发挥空间。

```python
async def generate_first_frame(shot: dict, image_api_key: str, image_base_url: str) -> str:
    """
    用 shot 的 final_video_prompt 生成一张静态图作为视频起始帧。
    返回图片 URL。
    """
    # 复用现有的 generate_image 函数
    from app.services.image import generate_image

    result = await generate_image(
        prompt=shot["final_video_prompt"],
        shot_id=shot["shot_id"],
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key=image_api_key,
        image_base_url=image_base_url,
    )
    return result["image_url"]
```

### API 支持情况

| 视频 API | 支持 image-to-video | 说明 |
|----------|-------------------|------|
| Kling | 是 | `image` 参数传入首帧 |
| Runway Gen-3/4 | 是 | `init_image` 参数 |
| Seedance | 部分 | 视版本 |
| Sora | 否（纯文生视频） | 不适用此策略 |

### 成本权衡

起始帧策略会增加一次图像生成调用（成本约 ¥0.01-0.05/张），但可以显著降低视频重跑率（减少因肢体崩坏导致的重试）。建议仅对 `scene_intensity: "high"` 的镜头启用。

---

## 九、换脸后处理（替代方案）

如果视频 API 或第三方服务支持换脸（FaceSwap），可作为 Visual DNA 的补充或替代：

- **与 Visual DNA 并用**：Prompt 层面保持一致性（Visual DNA），视频生成后再用参考图换脸进一步校正
- **替代 Visual DNA**：Prompt 中不再强调角色外貌，生成视频后统一换脸。适合对角色精度要求极高的场景

换脸的优势是面部一致性更高，劣势是增加后处理时间和成本，且对侧脸/遮挡场景效果有限。

---

## 十、完整调用链路

```python
async def generate_video_pipeline(
    script: str,
    character_info: dict,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    video_api_key: str,
    video_base_url: str,
    image_api_key: str = "",
    image_base_url: str = "",
    enable_judge: bool = True,
    enable_first_frame: bool = False,
    enable_negative: bool = True,
):
    """完整的视频生成管线。"""

    # Step 4: 分镜生成
    shots, usage = await parse_script_to_storyboard(
        script, provider, model, api_key, base_url, character_info
    )

    # Step 4.5: Judge Agent 审查（可选）
    if enable_judge:
        judge_result = await run_judge_agent(shots)
        if not judge_result["passed"]:
            # 携带 issues 重新生成（最多 1 次）
            shots, usage = await regenerate_with_feedback(
                script, judge_result["issues"], provider, model, api_key, base_url
            )

    # 提取 Visual DNA
    character_dna = {
        name: info.get("visual_dna", "")
        for name, info in character_info.get("character_images", {}).items()
        if info.get("visual_dna")
    }

    # Step 5: 后处理管线
    shots_data = [shot.model_dump() for shot in shots]
    shots_data = build_final_prompt(shots_data, character_dna, enable_negative)

    # 起始帧生成（可选，仅 high intensity）
    if enable_first_frame:
        for shot in shots_data:
            if shot.get("scene_intensity") == "high":
                shot["first_frame_url"] = await generate_first_frame(
                    shot, image_api_key, image_base_url
                )

    # 视频生成 API 调用
    videos = await generate_videos_batch(shots_data, video_api_key, video_base_url)

    return videos
```

---

## 十一、后续演进：DSPy 与 Generative Feedback Loops

### 11.1 DSPy 的建议挂载点

- 将角色外貌提取逻辑放在 `app/core/story_context.py` 的缓存构建阶段
- 目标输出继续落到 `Story.meta["character_appearance_cache"]`
- 生产环境只加载离线编译好的 DSPy 配置，不在请求链路实时 compile

### 11.2 建议的数据契约

```python
class CharacterAppearance(BaseModel):
    body: str
    clothing: str
```

对应现有运行时结构：

- `CharacterLock.body_features <- body`
- `CharacterLock.default_clothing <- clothing`

### 11.3 反馈闭环的建议挂载点

- 图片生成后：检查角色外貌、服装、主体数量是否满足 `CharacterLock`
- 视频生成后：检查起始帧一致性、动作完成度、尾帧目标状态是否满足要求
- 失败时只对当前 shot 增加纠错指令并有限次重试，不回滚整个 pipeline

### 11.4 成本控制原则

- 不对每个镜头默认全量质检
- 新角色首次出场必须检
- 大跨度换装必须检
- 同场景连续镜头建议每 3-5 镜抽检一次

### 11.5 当前状态

- `StoryContext` 与统一 payload 组装已进入主链路
- DSPy 提取器尚未接入
- VLM 质检与自动重试尚未接入
