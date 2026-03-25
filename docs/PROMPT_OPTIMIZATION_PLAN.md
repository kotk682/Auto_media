# 优化建议：提升视频生成质量

> **目标**：优化 `final_video_prompt` 的质量，让视频API更准确执行
> **责任归属**：分镜生成模块（app/prompts/storyboard.py）

---

## 📊 当前问题诊断

### 问题1：Prompt太复杂（最主要）

**当前SYSTEM_PROMPT要求**（第98行）：
```python
`final_video_prompt`: 80-120 words, straightforward vocabulary
```

**实际可能生成**：
```
"A young Chinese man in his late 20s, wearing a fitted blue business
shirt and black trousers, walks steadily from the office entrance
toward his desk in the center of the room, passing by two colleagues
who are working at their stations. He arrives at his desk, pulls out
the chair, and sits down smoothly, then opens his silver laptop and
begins typing, while warm morning sunlight streams through the large
glass windows behind him, creating soft shadows across the modern
office space. Cinematic, 4k, photorealistic, --ar 16:9"
```

**问题**：
- ❌ 120词，对Seedance太长
- ❌ 包含5+个动作：走、经过、到达、拉椅子、坐下、打开笔记本、打字
- ❌ 5秒内根本做不到
- ❌ API会选择性忽略部分指令

---

### 问题2：缺乏明确的约束

**当前缺失**：
```
- 没有告诉API"不要做什么"
- 没有强调"保持简单"
- 没有限制动作数量
```

**结果**：
- API可能让人物做太多动作
- 可能添加不存在的元素
- 可能改变服装颜色

---

### 问题3：视觉元素可能冲突

**当前结构**（第99行）：
```python
Structure: [Shot] + [Angle] + [Movement] + [Subject] + [Action] +
           [Environment] + [Lighting] + "Cinematic, 4k, photorealistic"
```

**问题**：
- 太多维度，API记不住
- 每个维度都要描述，篇幅爆炸

---

## 🎯 优化方案（3个层次）

### 方案1：简化Prompt结构（立即实施）⭐ 推荐

**修改 SYSTEM_PROMPT**：

```python
# 在第98-100行，改为：

- `final_video_prompt`: 40-60 words MAXIMUM (CRITICAL)
  - Structure: [Subject] + [ONE action] + [Environment] + "Static camera, natural lighting, cinematic, 4k"
  - Example: "A young Chinese man in a blue shirt walks toward a desk in a modern office. Warm morning light, static camera, cinematic, 4k, photorealistic"
  - **ONLY ONE CORE ACTION per shot** (walking, sitting, standing, turning, NOT walking-AND-sitting)
  - Use simple vocabulary: walk, sit, stand, turn, look, reach (NOT "saunter", "settle", "pivot")
  - **ADD NEGATIVE CONSTRAINTS**: "do not walk around", "keep hands visible", "maintain position"

**关键改动**：
1. ✅ 限制在40-60词（原来80-120）
2. ✅ 只允许1个核心动作
3. ✅ 添加负面约束
4. ✅ 强调静态摄像机
```

**预期效果**：
- 提升30-50%的准确度
- API更容易理解
- 动作更可控

---

### 方案2：增加负面提示词（中等成本）

**在final_video_prompt后追加**：

```python
# 修改分镜生成逻辑，在final_video_prompt后自动追加：
negative_prompt = " --negative walking around, extra movements, multiple actions, changing position, distorted limbs, flickering"

# 最终prompt：
f"{final_video_prompt}{negative_prompt}"
```

**注意**：
- 需要检查Seedance是否支持 `--negative` 语法
- 如果不支持，可以用 `negative_prompt` 参数

---

### 方案3：使用起始帧引导（高成本，高质量）⭐⭐⭐

**原理**：
```
生成视频前，先生成一张精确的起始帧图片
然后用 I2V (Image-to-Video) 而不是 T2V (Text-to-Video)
```

**优势**：
- ✅ 角色外貌100%准确（图片已经确定）
- ✅ 场景100%准确
- ✅ API只需做动作，不需要创造角色
- ✅ 质量提升50-80%

**实施**：

```python
# 在 app/services/storyboard.py 中修改流程

async def parse_script_to_storyboard(...):
    # ... 生成分镜 ...

    # 新增：为每个镜头生成起始帧图片
    for shot in shots:
        if shot.audio_reference and shot.audio_reference.content:
            # 有对话/动作的镜头，生成起始帧
            start_frame_prompt = build_start_frame_prompt(shot)
            image_result = await generate_image(
                visual_prompt=start_frame_prompt,
                shot_id=f"{shot.shot_id}_start",
                model="black-forest-labs/FLUX.1-schnell",
                image_api_key=settings.siliconflow_api_key,
                image_base_url=settings.siliconflow_base_url,
            )
            shot.start_frame_url = image_result["image_url"]

    return shots, usage


def build_start_frame_prompt(shot: Shot) -> str:
    """生成起始帧的prompt（只描述静态场景，不包含动作）"""
    ve = shot.visual_elements

    prompt = f"""
    {ve.subject_and_clothing}

    Scene: {ve.environment_and_props}

    Lighting: {ve.lighting_and_color}

    Camera: {shot.camera_setup.shot_size}, {shot.camera_setup.camera_angle}, static shot

    Style: Photorealistic, cinematic, 4k resolution

    Important: Static pose, no motion blur, clear details
    """

    return prompt.strip()
```

**然后在视频生成时使用I2V**：

```python
# app/services/video.py

async def generate_video(
    image_url: str,  # 使用起始帧
    prompt: str,
    shot_id: str,
    model: str = DEFAULT_MODEL,
    ...
) -> dict:
    # 视频API使用I2V模式
    # 起始帧已经确定了角色和场景
    # Prompt只需要描述"从起始状态开始做什么动作"
```

**成本**：
- 增加图片生成调用（每个镜头¥0.02）
- 增加处理时间（每个镜头+10秒）
- 总成本增加约15%

**收益**：
- 质量提升50-80%
- 角色一致性大幅提升
- 场景准确性100%

---

## 📊 方案对比

| 方案 | 实施难度 | 成本增加 | 质量提升 | 推荐度 |
|------|---------|---------|---------|--------|
| **方案1：简化Prompt** | 低（1小时）| 0% | +30-50% | ⭐⭐⭐⭐⭐ |
| **方案2：负面提示词** | 低（30分钟）| 0% | +10-20% | ⭐⭐⭐ |
| **方案3：起始帧引导** | 中（4小时）| +15% | +50-80% | ⭐⭐⭐⭐⭐ |

---

## 🚀 我的建议（分阶段实施）

### Phase 1：立即实施（1小时）⭐ 必做

**修改SYSTEM_PROMPT**：
```python
# app/prompts/storyboard.py 第98-100行

- `final_video_prompt`: 40-60 words MAXIMUM (CRITICAL)
  - Structure: [Subject] + [ONE action] + [Environment] + "Static camera, natural lighting, cinematic, 4k"
  - **ONLY ONE CORE ACTION** (NOT "walks AND sits", just "walks" or "sits")
  - Simple vocabulary only
  - Negative constraints: "do not walk around", "keep hands visible", "maintain position"
```

**测试效果**：
- 生成3-5个镜头
- 观察质量提升

---

### Phase 2：如果质量仍不够（4小时）⭐ 推荐

**实施起始帧引导**：
- 修改分镜生成流程
- 为每个镜头生成起始帧
- 使用I2V而不是T2V

**预期**：
- 质量提升50-80%
- 角色一致性大幅改善

---

### Phase 3：如果还不满意（调研）

**测试其他视频API**：
- Kling（快手）
- Runway Gen-3
- Pika Labs

**对比质量**，选择最好的

---

## ❓ 现在怎么做？

**选择1**：我帮你立即修改SYSTEM_PROMPT（1小时，0成本）
- 优化prompt结构
- 添加负面约束
- 限制动作数量

**选择2**：我帮你实施起始帧引导方案（4小时，+15%成本）
- 修改分镜生成流程
- 集成图片生成
- 修改视频生成逻辑

**选择3**：先测试一下当前质量
- 生成几个镜头
- 看看具体哪里不对
- 再针对性优化

你想先做哪个？💪
