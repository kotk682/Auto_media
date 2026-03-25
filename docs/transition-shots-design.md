# 过渡分镜设计方案 — 双向锚点受控生成 (Bi-Anchor Controlled Generation)

> 目标：通过插入过渡分镜 + 首尾帧物理约束，使场景内镜头切换和跨场景衔接丝滑无跳切。
> 相关文件：`app/schemas/storyboard.py`、`app/prompts/storyboard.py`、`app/services/video.py`、`app/services/pipeline_executor.py`
> 更新日期：2026-03-24

---

## 一、核心架构：3+2+1 序列

每个场景拆解为三层结构：

| 层级 | 镜头类型 | 每场景数量 | 生成模式 | 核心任务 |
| :--- | :--- | :--- | :--- | :--- |
| **骨架** | 主镜 (Main Shot) | 3 | I2V / T2V | 交代核心剧情、台词、关键动作 |
| **肌肉** | 场景内过渡镜 (Internal Transition) | 2 | Dual-Frame I2V | 利用前镜尾帧 + 后镜首帧补全动作位移 |
| **皮肤** | 跨场景桥接镜 (Scene Bridge) | 1（每两个场景之间） | I2V / T2V | 处理时空/环境切换，提供视觉呼吸 |

最终播放序列：

```text
scene1_shot1 → [scene1_trans1] → scene1_shot2 → [scene1_trans2] → scene1_shot3
                                                                        ↓
                                                          [trans_scene1_scene2]  ← 跨场景桥接
                                                                        ↓
scene2_shot1 → [scene2_trans1] → scene2_shot2 → [scene2_trans2] → scene2_shot3
```

---

## 二、过渡分镜生成原理：双帧补全法

### 2.1 物理约束

过渡分镜不再"凭空想象"，而是用前后主镜的帧作为物理锚点：

- **输入**：前镜最后一帧 (A_end) + 后镜第一帧 (B_start) + 文本辅助指令 (Text Aid)
- **原理**：AI 从 A 状态演变到 B 状态的最短物理路径，首尾帧锁死起止位置，形变被压缩在极短时间内

### 2.2 两阶段生成流程

```text
Phase 1：并行生成主镜
  scene1_shot1、scene1_shot2、scene1_shot3 同时生成（场景间并行）

Phase 2：串行生成过渡镜
  主镜全部完成后 → FFmpeg 提取 A_end / B_start
  → 将首尾帧 + transition_text_aid 送入 Dual-Frame I2V API
  → 生成过渡片段
```

### 2.3 文本辅助指令 (Text Aid)

有了首尾帧约束后，文本不再需要描述主体外观，只需描述 **"力的相互作用"**，分为三类：

| 类别 | 用途 | 指令词 |
| :--- | :--- | :--- |
| 动力学 (Dynamics) | 补全动作惯性 | `Momentum interpolation`, `Kinetic flow`, `Action completion` |
| 运镜 (Camera) | 景别/焦点平滑切换 | `Focal shift`, `Dynamic reframing`, `Parallax` |
| 遮效 (Masking) | 首尾帧差异过大时掩盖形变 | `Visual obscuration`, `Light manipulation` |

---

## 三、高级视觉优化策略

### 3.1 动量匹配 (Motion Matching)

- 如果主镜 A 以高速运动结束，过渡镜必须带有运动模糊
- 自动计算两个主镜的"视觉位移矢量"，位移越大，过渡镜的动作幅度 (Motion Bucket) 参数越高

### 3.2 相似性转场 (Match Cut)

- **场景内**：利用首尾帧中重合度最高的物体（如手中的杯子、角色面部）作为视觉锚点，补帧时强制锁定这些像素不产生剧烈位移
- **场景间**：寻找颜色、形状相似的物体进行桥接过渡（例如：圆形的表盘 → 圆形的井盖）

### 3.3 光影色彩对齐

- 后端提取 A_end 和 B_start 的平均色调，差异过大时自动在辅助文本中追加 `"Light-to-dark transition"` 或 `"Lens flare flash"` 消解色偏
- 如果 I2V API 支持 `color_reference`，传入主镜 A 的图片防止过渡镜变色

### 3.4 安全原则：宁模糊，不扭曲

模糊看起来像摄影技术，扭曲看起来像系统崩溃。当首尾帧差异过大时，优先使用运动模糊、光晕闪白、前景遮挡等手法掩盖。

---

## 四、数据结构变更

### 4.1 Shot Schema 新增字段

**文件**：`app/schemas/storyboard.py`

```python
is_transition: bool = Field(default=False, description="是否为过渡分镜")
transition_type: Optional[str] = Field(
    default=None,
    description="过渡类型: 'intra_scene'（场景内）| 'inter_scene'（跨场景桥接）"
)
transition_logic: Optional[str] = Field(
    default=None,
    description="过渡逻辑: 'motion_matching' | 'cinematic_camera' | 'masking' | 'scene_bridge'"
)
transition_text_aid: Optional[str] = Field(
    default=None,
    description="过渡辅助指令，描述力/运镜/遮效，直接拼入视频生成 prompt"
)
reference_frames: Optional[dict] = Field(
    default=None,
    description="首尾帧引用: { 'start_frame': 前镜尾帧路径, 'end_frame': 后镜首帧路径 }"
)
```

### 4.2 shot_id 命名约定

| 类型 | 格式示例 | 说明 |
|------|----------|------|
| 主镜头 | `scene1_shot1` | 现有格式不变 |
| 场景内过渡 | `scene1_trans1` | `trans` 代替 `shot`，编号从 1 起 |
| 跨场景桥接 | `trans_scene1_scene2` | 标明连接的两个场景 |

---

## 五、分镜 Prompt 变更

### 5.1 SYSTEM_PROMPT 新增 Law 6

**文件**：`app/prompts/storyboard.py`

```text
**Law 6 — 3+2+1 分镜结构规范**

每个场景必须包含且仅包含 **3 个主镜头**（scene{N}_shot1/2/3）。

除主镜头外，按如下规则同时输出过渡分镜：

**场景内过渡分镜**（transition_type: "intra_scene"）：
- 每个场景生成 2 个，插入在 shot1→shot2 和 shot2→shot3 之间
- shot_id 格式：scene{N}_trans1、scene{N}_trans2
- 约束：
  - estimated_duration：2 秒
  - scene_intensity：固定 "low"
  - is_transition：true
  - transition_logic：根据前后主镜的物理差异选择：
    "motion_matching"（动作连续）| "cinematic_camera"（景别变化）| "masking"（差异过大需遮效）
  - transition_text_aid：只描述力/运动/遮效指令，不描述主体外观（首尾帧已约束外观）
  - final_video_prompt：组合过渡运动描述 + transition_text_aid
  - camera_setup.movement：优先 "Slow Dolly in" / "Dolly out" / "Pan" 等平滑运动

**跨场景桥接分镜**（transition_type: "inter_scene"）：
- 在两个相邻场景之间各生成 1 个
- shot_id 格式：trans_scene{N}_scene{N+1}
- 约束：
  - estimated_duration：2 秒
  - scene_intensity：固定 "low"
  - is_transition：true
  - transition_logic：固定 "scene_bridge"
  - transition_text_aid：以时空过渡意象为主（时间流逝、空镜、氛围叠化）
  - final_video_prompt：以上一场景末镜视觉元素渐出、下一场景首镜视觉元素渐入为重点
```

### 5.2 USER_TEMPLATE 输出格式约束

```text
输出 JSON 数组按最终播放顺序排列所有镜头（含过渡），顺序如下：
  scene1_shot1 → scene1_trans1 → scene1_shot2 → scene1_trans2 → scene1_shot3
  → trans_scene1_scene2
  → scene2_shot1 → scene2_trans1 → ...
```

### 5.3 `_parse_shots` 兼容处理

**文件**：`app/services/storyboard.py`

```python
# 兜底：从 shot_id 自动推断 is_transition（防止 LLM 遗漏）
if "is_transition" not in item:
    shot_id = item.get("shot_id", "")
    item["is_transition"] = ("_trans" in shot_id) or shot_id.startswith("trans_")
if item.get("is_transition") and "transition_type" not in item:
    shot_id = item.get("shot_id", "")
    item["transition_type"] = "inter_scene" if shot_id.startswith("trans_") else "intra_scene"
```

---

## 六、过渡辅助指令库

LLM 在生成过渡分镜的 `transition_text_aid` 时，根据 `transition_logic` 从以下指令库中选用：

### 6.1 动力学衔接类 (motion_matching)

用于同一场景内两个主镜动作之间的物理补全。

| 场景 | 推荐指令 |
| :--- | :--- |
| 手部动作 | `Seamlessly interpolate the hand reaching motion, maintain anatomical consistency.` |
| 起身/跳跃 | `Execute the upward explosive force, matching the velocity of the previous shot.` |
| 行走步态 | `Continue the walking gait with natural rhythmic swaying of the torso.` |

### 6.2 电影感运镜类 (cinematic_camera)

用于景别切换或视觉焦点改变时的平滑过渡。

| 场景 | 推荐指令 |
| :--- | :--- |
| 甩镜头转场 | `Fast cinematic whip pan, creating directional motion blur to bridge the two positions.` |
| 快速推近 | `Aggressive dolly-in to the subject's eyes, matching the start frame of the next shot.` |
| 环绕运镜 | `360-degree orbital rotation, maintaining the subject at the center of the frame.` |

### 6.3 遮效类 (masking)

首尾帧差异过大、AI 可能产生形变时，用特效掩盖瑕疵。

| 场景 | 推荐指令 |
| :--- | :--- |
| 重度模糊 | `Apply heavy directional motion blur to mask any potential anatomical morphing.` |
| 光晕闪白 | `Intense lens flare flash, blooming from the center to create an optical transition.` |
| 前景遮挡 | `A dark foreground object passes quickly across the camera, creating a natural wipe.` |

### 6.4 跨场桥接类 (scene_bridge)

两个完全不同场景之间的意象衔接。

| 场景 | 推荐指令 |
| :--- | :--- |
| 时间流逝 | `Time-lapse shadow movement across the wall, fading from day to night.` |
| 微粒过渡 | `Ethereal dust particles floating in a light beam, transitioning the viewer's focus.` |
| 极简空镜 | `Extreme close-up of a ticking clock/flickering neon sign, symbolizing the scene shift.` |

---

## 七、视频生成变更

### 7.1 场景分组逻辑

**文件**：`app/services/video.py` — `group_shots_by_scene`

```python
def group_shots_by_scene(shots: list[dict]) -> OrderedDict:
    """
    - scene{N}_shot{M} / scene{N}_trans{M}  → scene{N}
    - trans_scene{N}_scene{N+1}             → 独立分组，key 为 shot_id
    """
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for shot in shots:
        sid = shot["shot_id"]
        if sid.startswith("trans_scene"):
            groups[sid] = [shot]
        else:
            match = re.match(r"(scene\d+)", sid)
            scene_key = match.group(1) if match else "scene0"
            groups.setdefault(scene_key, []).append(shot)
    return groups
```

### 7.2 链式生成两阶段改造（目标设计，待实现）

**文件**：`app/services/video.py` — `generate_videos_chained`

目标设计（待实现）：

```text
Phase 1：场景间并行，场景内串行生成主镜头
  for each scene (并行):
    for each main shot (串行):
      首镜头 → generate_image() → generate_video() → extract_last_frame()
      后续镜头 → 复用 prev_frame → generate_video() → extract_last_frame()

Phase 2：生成过渡分镜
  主镜头全部完成后：
  for each transition shot:
    FFmpeg 提取 A_end（前镜最后一帧）
    FFmpeg 提取 B_start（后镜第一帧）
    prompt = transition_text_aid（不含主体描述，仅力/运镜/遮效）
    generate_video(image=A_end, prompt=prompt)  # Dual-Frame I2V（如 API 支持则同时传 B_start）
```

```python
async def _process_scene(scene_key: str, scene_shots: list[dict]) -> list[dict]:
    ...
    for idx, shot in enumerate(scene_shots):
        is_transition = shot.get("is_transition", False)

        if is_transition:
            # 过渡分镜强制使用前镜尾帧
            if prev_frame_path is None:
                logger.warning("过渡分镜 %s 缺少前置帧，将跳过", shot["shot_id"])
                continue
            # prompt 使用 transition_text_aid（力/运镜/遮效），不重复描述主体
            prompt = shot.get("transition_text_aid") or shot.get("final_video_prompt", "")
        else:
            # 主镜头正常逻辑
            prompt = f"{visual_prompt} {camera_motion}"
        ...
```

### 7.3 `generate_videos_batch` 兼容

已在 2026-03-24 修复 `.get()` 回退，过渡分镜和主镜头共用同一逻辑，无需额外修改。

---

## 八、流水线执行变更

**文件**：`app/services/pipeline_executor.py`

### 8.1 TTS 过滤过渡分镜

```python
# 在 _run_separated_strategy / _run_chained_strategy 的 TTS 步骤：
tts_shots = [s for s in self.shots if not s.is_transition]
tts_results = await tts.generate_tts_batch(tts_shots, ...)
```

### 8.2 FFmpeg 合成：过渡分镜透传无声视频

```python
for result in results:
    shot = shot_map.get(result["shot_id"])
    if shot and shot.get("is_transition"):
        result["final_video_url"] = result["video_url"]  # 无声直接用
        continue
    # 正常 stitch（音视频合成）
    ...
```

### 8.3 播放顺序保证

LLM 按播放顺序输出 JSON → `_parse_shots` 保持顺序 → `generate_videos_chained` 按 `shot_order` 展平。前端 concat 同样按 shot 顺序传入 `video_urls`，无需额外排序。

---

## 九、前端变更

**文件**：`frontend/src/views/VideoGeneration.vue`

- 过渡分镜卡片通过 `shot.is_transition` 区分，默认折叠收起，样式灰显
- 过渡分镜不展示台词 / TTS 控件
- "生成视频"按钮对过渡分镜和主镜头均生效

---

## 十、变更文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/schemas/storyboard.py` | 新增字段 | `is_transition`, `transition_type`, `transition_logic`, `transition_text_aid`, `reference_frames` |
| `app/prompts/storyboard.py` | Prompt 追加 | Law 6（3+2+1 结构 + 指令库引用） |
| `app/services/storyboard.py` | 兼容补丁 | `_parse_shots` 自动推断 `is_transition` |
| `app/services/video.py` | 核心改造 | `group_shots_by_scene` 支持跨场景分组；链式生成两阶段改造 |
| `app/services/pipeline_executor.py` | 过滤逻辑 | TTS 跳过过渡分镜；stitch 透传无声视频 |
| `app/services/ffmpeg.py` | 新增函数 | `extract_first_frame()` 提取首帧（Phase 2 用） |
| `frontend/src/views/VideoGeneration.vue` | UI 区分 | 过渡分镜卡片折叠 + 样式差异化 |

---

## 十一、最终视频结构示意

以 2 个场景为例：

```text
[scene1_shot1]          4s  主镜头
[scene1_trans1]         2s  ← 场景内过渡（A_end + B_start 约束）
[scene1_shot2]          4s  主镜头
[scene1_trans2]         2s  ← 场景内过渡（A_end + B_start 约束）
[scene1_shot3]          4s  主镜头
[trans_scene1_scene2]   2s  ← 跨场景桥接（空镜/意象衔接）
[scene2_shot1]          4s  主镜头
[scene2_trans1]         2s  ← 场景内过渡
[scene2_shot2]          4s  主镜头
[scene2_trans2]         2s  ← 场景内过渡
[scene2_shot3]          4s  主镜头

总时长：2×(3×4 + 2×2) + 1×2 = 34s
```

---

## 十二、落地注意事项

1. **帧率匹配**：过渡视频与主镜视频 FPS 必须一致（统一 24 或 30），否则 concat 后有明显卡顿
2. **色彩对齐**：如果 I2V API 支持 `color_reference`，传入前镜图片防止过渡镜变色
3. **API 能力适配**：Dual-Frame I2V（同时接受首尾帧）是理想方案；如果当前 API 仅支持单图 I2V，退化为仅使用 A_end 作为参考图，prompt 中显式描述向 B_start 的运动方向

---

## 十三、已知冲突与待解决项

> 以下为代码审计发现的问题，实施前必须逐项处理。

### 13.1 已修复的 BUG (2026-03-24)

`_run_chained_strategy` 中有 3 处字段名与 Shot schema 不一致，已修复：

| 原错误代码 | 修复为 | 说明 |
|------------|--------|------|
| `s.dialogue` | `s.audio_reference.content`（含 type 判断） | Shot 无 `dialogue` 字段 |
| `s.visual_prompt` | `s.final_video_prompt` | Shot 无 `visual_prompt` 字段 |
| `s.camera_motion` | `s.camera_setup.movement` | Shot 无 `camera_motion` 字段 |

### 13.2 两阶段 vs 单阶段：现状单阶段，需迁移

当前 `generate_videos_chained` 是**单阶段**（场景内串行遍历所有 shot，尚不区分主镜头与过渡分镜）。实现文档中的两阶段需要以下额外工作：

1. Phase 1 入口需要**过滤掉** `is_transition=True` 的 shot，仅处理主镜头
2. Phase 1 完成后，对所有主镜头视频提取首帧和尾帧
3. Phase 2 遍历过渡分镜，匹配前后主镜头的帧作为输入
4. 最终按原始 shot 顺序**重组**主镜头 + 过渡镜头结果

建议实施方案：在 `generate_videos_chained` 内部拆分而非改签名，对外接口不变。

```python
async def generate_videos_chained(shots, ...):
    main_shots = [s for s in shots if not s.get("is_transition")]
    transition_shots = [s for s in shots if s.get("is_transition")]

    # Phase 1: 链式生成主镜头（现有逻辑）
    main_results = await _generate_main_shots(main_shots, ...)
    main_map = {r["shot_id"]: r for r in main_results}

    # Phase 2: 生成过渡镜头
    trans_results = await _generate_transitions(transition_shots, main_map, ...)

    # 按原始顺序合并
    all_results = main_results + trans_results
    return _reorder_by_original(shots, all_results)
```

### 13.3 `group_shots_by_scene` 修改范围

在两阶段方案下，`group_shots_by_scene` 仅在 Phase 1 被调用（只处理主镜头），不需要识别 `trans_scene*` 前缀。跨场景过渡在 Phase 2 中单独处理。

因此 `group_shots_by_scene` 的改动可简化为：仅确保 `scene{N}_trans{M}` 正确归入 `scene{N}`（Phase 1 过滤后实际不会出现，但作为防御）。

### 13.4 `generate_video()` 需支持可选双帧输入

当前签名只接受单张 `image_url`。为支持 Dual-Frame I2V，需：

```python
async def generate_video(
    image_url: str,
    prompt: str,
    shot_id: str,
    end_frame_url: Optional[str] = None,  # 新增：后镜首帧（可选）
    ...
) -> dict:
```

同时 video provider 接口需适配：

```python
# app/services/video_providers/base.py 或 factory.py
class VideoProvider:
    async def generate(self, image_url, prompt, model, ..., end_frame_url=None):
        ...
```

降级策略：`end_frame_url` 为 None 时走现有单帧逻辑。

### 13.5 `ffmpeg.py` 新增 `extract_first_frame()`

Phase 2 需要后镜首帧 (B_start)，需新增：

```python
async def extract_first_frame(video_path: str, shot_id: str) -> str:
    """提取视频第一帧，输出到 media/images/{shot_id}_firstframe.png"""
    output = IMAGE_DIR / f"{shot_id}_firstframe.png"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        str(output),
    ]
    ...
    return str(output)
```

### 13.6 `VisualElements` 对过渡分镜不适用

当前 `visual_elements: VisualElements` 是 Shot 的 **required** 字段（含 4 个子字段）。过渡分镜没有主体描述，需要处理：

**方案 A**（推荐）：将 `visual_elements` 改为 Optional

```python
visual_elements: Optional[VisualElements] = Field(default=None, ...)
```

**方案 B**：在 Prompt Law 6 中指定过渡分镜的 `visual_elements` 填写规范（如环境描述复用前镜）。

### 13.7 `transition_from_previous` 字段与新字段关系

Shot schema 已有 `transition_from_previous: Optional[str]`（描述与前镜的过渡关系）。新增的 `is_transition` / `transition_type` / `transition_text_aid` 服务于**独立的过渡分镜**。

明确分工：
- `transition_from_previous`：保留，用于**主镜头**描述与前一主镜头的叙事衔接（供 LLM 保持连贯性）
- `is_transition` 等新字段：仅用于**过渡分镜**的生成控制

### 13.8 SEPARATED / INTEGRATED 策略的过渡分镜处理

LLM 输出统一包含过渡分镜（不区分策略），因此三种策略都需要处理：

| 策略 | 过渡分镜处理方式 |
|------|-----------------|
| **CHAINED** | 两阶段：Phase 1 主镜头链式 → Phase 2 双帧约束生成过渡（完整能力） |
| **SEPARATED** | 降级：过渡分镜与主镜头一起并行生成图片和视频，不做双帧约束（无链式帧传递） |
| **INTEGRATED** | 降级：同 SEPARATED |

所有策略通用：
- TTS 步骤跳过 `is_transition=True` 的 shot
- stitch 步骤过渡分镜透传无声视频
- concat 步骤按原始 shot 顺序拼接

### 13.9 Prompt Law 6 需补充的字段约束

当前 Law 6 未规定过渡分镜的 `audio_reference` 和 `visual_elements`，LLM 可能会乱填。需追加：

```
过渡分镜字段约束：
- audio_reference：必须为 null（过渡分镜无台词/旁白）
- visual_elements：可省略或复用前一主镜头的环境描述，subject_and_clothing 留空
- mood：可选，与前后主镜头保持一致
- storyboard_description：简要描述过渡效果（如"快速推近过渡到下一镜头"）
```

### 13.10 遗漏的变更文件

| 文件 | 需要修改 | 说明 |
|------|----------|------|
| `app/routers/video.py` | 是 | 前端单镜头视频生成入口，当前直接调 `generate_videos_batch()`，不走 Dual-Frame 逻辑；需对 `is_transition` 的 shot 走独立路径或标注为仅支持降级模式 |
| `app/services/video_providers/*.py` | 是 | Provider 接口需新增 `end_frame_url` 可选参数（dashscope / minimax 等） |
| `app/services/tts.py` | 确认 | `generate_tts_batch` 需确认对 `dialogue=None` 的 shot 是否安全跳过 |
| `app/routers/pipeline.py` | 是 | `render_video`、`generate_assets` 等手动端点也需跳过过渡分镜的 TTS，透传无声视频 |
| `app/schemas/pipeline.py` | 可选 | `ShotResult` 可新增 `is_transition` 字段，便于前端区分 |

---

## 十四、方案评估与风险分析

> 更新日期：2026-03-24
> 评估人：Claude Code（基于代码审计和架构分析）

### 14.1 总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **理论先进性** | 9/10 | 双帧约束是业界前沿思路，符合最新研究方向 |
| **文档完整性** | 10/10 | 工业级文档质量，覆盖架构、数据结构、变更清单 |
| **实现完整度** | 0/10 | 完全未开始实施 |
| **技术可行性** | 4/10 | API能力假设过于乐观，存在重大技术风险 |
| **工程复杂度** | 3/10 | 改动范围过大（10+文件），测试和调试成本高 |
| **成本效益** | 5/10 | 成本增加83%，质量提升未经验证 |

**综合评分：5.2/10**

---

### 14.2 核心优势

#### ✅ 理论设计先进

- **双帧物理约束**：用首尾帧锚定起止状态，AI只需补全中间插值，这是视频生成的正确方向
- **3+2+1层次结构**：符合电影剪辑理论（骨架/肌肉/皮肤的比喻很恰当）
- **四类过渡逻辑**：motion_matching/cinematic_camera/masking/scene_bridge 覆盖了实际需求
- **指令库设计**：transition_text_aid 只描述"力"而不重复主体，思路正确

#### ✅ 文档质量极高

- 535行设计文档，涵盖完整实施细节
- 第13节"已知冲突"非常专业，说明做过深入代码审计
- 变更文件清单、字段对照表完整，可直接作为实施指南

---

### 14.3 严重问题与风险

#### ❌ 1. 实现完整度为零

**现状**（截至 2026-03-24）：
```python
# app/schemas/storyboard.py
class Shot(BaseModel):
    # 完全缺少过渡分镜字段：
    # - is_transition
    # - transition_type
    # - transition_logic
    # - transition_text_aid
    # - reference_frames
```

**代码审计结果**：
- `generate_videos_chained()` 只有单阶段逻辑，未拆分 Phase1/Phase2
- `generate_video()` 签名不支持双帧输入（缺少 `end_frame_url`）
- `ffmpeg.py` 没有 `extract_first_frame()` 函数
- 所有 provider 接口（dashscope/minimax等）都不支持双帧参数

**预计工作量**：
- 后端改动：10+ 文件，500+ 行代码
- 前端改动：3+ 文件（过渡分镜UI差异化）
- 测试用例：需要覆盖3种策略 × 过渡分镜逻辑
- **预计开发周期**：2-3周（含调试和测试）

---

#### ⚠️ 2. API能力假设过于乐观（最大技术风险）

文档假设视频API支持 **Dual-Frame I2V**（同时接受首尾帧），但：

**当前业界现状**：

| API | 支持双帧输入 | 支持单帧I2V | 说明 |
|-----|------------|------------|------|
| **Kling** | ❌ 不支持 | ✅ | 只接受 `image` 参数（单张起始帧） |
| **Runway Gen-3/4** | ❌ 不支持 | ✅ | 只接受 `init_image`（单张） |
| **Seedance 1.5** | ❌ 未知 | ✅ | 文档未提及双帧能力，需实测验证 |
| **Pika** | ❌ 不支持 | ✅ | 只支持单图I2V |
| **Sora** | ❌ 纯文生视频 | ❌ | 不支持任何图片输入 |

**风险**：
- 如果主流API都不支持双帧，整个方案的核心机制无法落地
- 只能退化为"单帧 + prompt描述尾帧"的模拟方案，质量大打折扣

**建议**：在第十五节提供API能力验证demo，先实测再决定技术路线。

---

#### ⚠️ 3. 工程复杂度极高

**改动范围**：
```
后端核心逻辑：
  - app/schemas/storyboard.py（新增5个字段）
  - app/prompts/storyboard.py（追加Law 6）
  - app/services/storyboard.py（_parse_shots 兼容）
  - app/services/video.py（重构 generate_videos_chained）
  - app/services/ffmpeg.py（新增 extract_first_frame）
  - app/services/video_providers/factory.py（接口改造）
  - app/services/video_providers/dashscope.py（适配双帧）
  - app/services/video_providers/minimax.py（适配双帧）
  - app/services/pipeline_executor.py（TTS/ Stitch过滤）
  - app/routers/video.py（单镜头入口适配）
  - app/routers/pipeline.py（手动端点适配）

前端UI：
  - frontend/src/views/VideoGeneration.vue（过渡分镜卡片）
  - 前端组件库（可能需要新的折叠组件）

测试：
  - 单元测试：过渡逻辑分类、两阶段流程
  - 集成测试：3种策略 × 过渡分镜
  - E2E测试：完整管线
```

**风险**：
- 改动链路过长，任何一环出错都会阻塞整体
- 向后兼容性：需要考虑已有分镜数据（没有 is_transition 字段）的处理
- 调试困难：两阶段流程的时序问题难以排查

---

#### ⚠️ 4. 成本控制问题

**成本增加计算**（以2场景为例）：

```
原方案（无过渡分镜）：
  - 6个主镜头 × (图片¥0.02 + 视频¥0.15) = ¥1.02

新方案（含过渡分镜）：
  - 6主镜 + 4场内过渡 + 1跨场景桥接 = 11个视频
  - 11 × (图片¥0.02 + 视频¥0.15) = ¥1.87
  - 成本增加：83%

额外开销：
  - FFmpeg 帧提取（计算资源）
  - 过渡分镜的存储空间
  - API调用次数增加 → 失败率相应提升
```

**问题**：
- 视频API可能按4-5秒收费，无法精确控制到2秒
- 没有ROI分析：83%的成本增加能换来多少质量提升？
- 用户可能不愿意为过渡分镜买单

**建议**：
- 添加配置开关：`enable_transition_shots: bool = False`（默认关闭）
- 仅对 `scene_intensity: "high"` 的镜头启用过渡（成本可控）

---

#### ⚠️ 5. 降级策略不清晰

文档提到 SEPARATED/INTEGRATED 策略下过渡分镜"降级"，但：

**问题**：
- 降级后如何保证过渡质量？
- 如果降级到和主镜头一样并行生成，双帧约束的价值在哪？
- 用户体验割裂：同一系统在不同策略下质量差异巨大

**建议**：
- 明确降级方案的具体逻辑（如改用运动模糊滤镜代替双帧）
- 或者只保留CHAINED策略，放弃SEPARATED/INTEGRATED的过渡分镜支持

---

### 14.4 设计缺陷

#### 1. Schema 设计冲突

**问题**：
```python
# 文档要求过渡分镜 visual_elements 改为 Optional
visual_elements: Optional[VisualElements] = Field(default=None, ...)

# 但 VisualElements 所有字段都是 required
class VisualElements(BaseModel):
    subject_and_clothing: str  # required
    action_and_expression: str  # required
```

Pydantic 无法区分"整个对象Optional"和"字段Optional"。

**建议**：
```python
class VisualElements(BaseModel):
    subject_and_clothing: Optional[str] = None
    action_and_expression: Optional[str] = None
    environment_and_props: Optional[str] = None
    lighting_and_color: Optional[str] = None
```

---

#### 2. LLM可控性存疑

**问题**：
- Prompt Law 6 要求LLM自动判断 `transition_logic`（motion_matching/cinematic_camera/masking）
- 这需要LLM对前后主镜的视觉差异做**物理推理**，能力要求极高
- 实际可能：LLM随机选择或全部填写"masking"逃避判断

**建议**：
```python
# 不要让LLM判断，而是用规则：
def infer_transition_logic(prev_shot: dict, next_shot: dict) -> str:
    """根据前后镜头差异自动推断过渡逻辑"""
    # 景别变化 > 2级 → cinematic_camera
    if abs(SHOT_SIZE_ORDER[prev_shot.camera_setup.shot_size] -
           SHOT_SIZE_ORDER[next_shot.camera_setup.shot_size]) > 2:
        return "cinematic_camera"

    # 主体位置差异 > 阈值 → motion_matching
    if has_large_subject_displacement(prev_shot, next_shot):
        return "motion_matching"

    # 默认 → masking
    return "masking"
```

---

#### 3. 时序依赖未充分考虑

**问题**：
```
Phase 1: scene1_shot1 → shot2 → shot3 (串行)
Phase 2: 提取所有帧 → 生成过渡
```

- 如果 scene1_shot2 生成失败，整个场景的过渡分镜都无法生成
- 没有错误恢复机制
- 串行生成时间：原方案6视频×30秒=3分钟 → 新方案可能需要5-6分钟

**建议**：
```python
# 添加失败回退
async def generate_transition(transition_shot: dict) -> Optional[dict]:
    try:
        return await _generate_with_dual_frame(transition_shot)
    except Exception as e:
        logger.warning(f"过渡分镜 {transition_shot['shot_id']} 生成失败: {e}")
        return None  # FFmpeg concat 时会自动跳过 None

# 或者用静态图填充
except Exception:
    return create_static_transition(transition_shot)  # 2秒静态图
```

---

### 14.5 分阶段实施建议（MVP优先）

#### Phase 0：技术验证（1-2天）

**目标**：验证API是否支持双帧输入

1. 编写API能力探测脚本（见第十五节）
2. 实测 Kling / Runway / Seedance 的双帧支持情况
3. 如果都不支持，评估替代方案：
   - 方案A：单帧 + prompt描述尾帧状态
   - 方案B：视频生成后用插帧模型（如RIFE/FFmpeg minterpolate）后处理
   - 方案C：放弃过渡分镜，改用更长的主镜头 + 淡入淡出

**决策点**：
- 如果API不支持双帧 → 暂停实施，先做替代方案POC
- 如果API支持 → 进入 Phase 1

---

#### Phase 1：最小可行方案（3-5天）

**范围**：仅实现跨场景桥接（trans_scene1_scene2）

**改动**：
```python
# 只新增必要字段
class Shot(BaseModel):
    is_transition: bool = False
    transition_type: Optional[str] = None  # 仅支持 "inter_scene"

# Prompt 只追加跨场景桥接规则（不做场内过渡）
# Law 6 简化版：仅在相邻场景间插入1个2秒空镜
```

**优势**：
- 改动范围小（3-5个文件）
- 不影响主镜头生成逻辑
- 易于测试和回滚
- 可快速验证流程和质量

**评估指标**：
- 过渡分镜生成成功率 > 80%
- 用户满意度调研
- 视觉连贯性评分（A/B测试）

---

#### Phase 2：完整实现（1-2周）

**前置条件**：Phase 1 验证成功

**范围**：
- 场内过渡分镜（scene1_trans1/2）
- 两阶段流水线（Phase1主镜 → Phase2过渡）
- 完整的 Schema 和 Prompt Law 6
- 前端UI差异化

**质量保证**：
- 单元测试覆盖率 > 80%
- E2E测试：至少3种场景类型（对话/动作/风景）
- 性能测试：两阶段流程的耗时优化

---

### 14.6 替代方案对比

| 方案 | 优势 | 劣势 | 成本 | 质量 |
|------|------|------|------|------|
| **当前方案（双帧I2V）** | 理论最优 | API可能不支持 | 高 | 理论最高 |
| **单帧 + Prompt** | API友好 | 质量不稳定 | 中 | 中 |
| **视频插帧后处理** | 不依赖API | 计算开销大 | 高 | 中 |
| **淡入淡出滤镜** | 实现简单 | 艺术感弱 | 低 | 低 |
| **延长主镜头** | 无额外成本 | 镜头冗长 | 无变化 | 取决于内容 |

**推荐**：
1. 先做 Phase 0 验证
2. 根据API能力选择方案
3. 如果API不支持双帧，建议采用 **单帧 + Prompt + 运动模糊滤镜** 的混合方案

---

## 十五、API能力验证 Demo

> 本节提供实测脚本，用于验证视频API是否支持双帧输入。

### 15.1 测试目标

验证以下API的输入参数：
- 是否支持 `image` 参数（起始帧）
- 是否支持 `end_frame` / `reference_frame` 参数（结束帧）
- 如果不支持，是否可以通过其他方式模拟（如 `prompt` 中描述尾帧）

### 15.2 测试脚本

**文件**：`tests/api_capability_test.py`

```python
"""
API双帧能力验证脚本
用法：python tests/api_capability_test.py --provider dashscope --model wanx2.1-i2v
"""

import asyncio
import argparse
from pathlib import Path
from app.services.video_providers.factory import get_video_provider
from app.services.ffmpeg import extract_last_frame

# 测试图片（需要提前准备）
START_FRAME = "media/test_images/start_frame.png"
END_FRAME = "media/test_images/end_frame.png"
OUTPUT_DIR = Path("media/test_outputs")


async def test_single_frame_capability(provider_name: str, model: str, api_key: str, base_url: str):
    """测试单帧I2V能力"""
    print(f"\n[测试1] 单帧I2V能力 - {provider_name}/{model}")
    print(f"  输入：{START_FRAME}")

    provider = get_video_provider(provider_name)

    try:
        video_url = await provider.generate(
            image_url=START_FRAME,
            prompt="A person walking forward naturally",
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        print(f"  ✅ 单帧I2V支持")
        print(f"  输出：{video_url}")
        return True
    except Exception as e:
        print(f"  ❌ 单帧I2V不支持或失败：{e}")
        return False


async def test_dual_frame_capability(provider_name: str, model: str, api_key: str, base_url: str):
    """测试双帧输入能力"""
    print(f"\n[测试2] 双帧输入能力 - {provider_name}/{model}")
    print(f"  起始帧：{START_FRAME}")
    print(f"  结束帧：{END_FRAME}")

    provider = get_video_provider(provider_name)

    # 检查 provider 接口是否支持 end_frame_url 参数
    import inspect
    sig = inspect.signature(provider.generate)
    params = list(sig.parameters.keys())

    if "end_frame_url" in params or "reference_frame" in params:
        print(f"  ℹ️  接口支持参数：{[p for p in params if 'frame' in p or 'reference' in p]}")

        try:
            # 尝试传入双帧
            video_url = await provider.generate(
                image_url=START_FRAME,
                end_frame_url=END_FRAME,  # 尝试传入结束帧
                prompt="Transition from start pose to end pose",
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            print(f"  ✅ 双帧输入支持")
            print(f"  输出：{video_url}")
            return True
        except TypeError as e:
            print(f"  ❌ 接口签名支持但调用失败：{e}")
            return False
        except Exception as e:
            print(f"  ⚠️  接口支持但生成失败：{e}")
            return False
    else:
        print(f"  ❌ 接口不支持双帧参数")
        print(f"  可用参数：{params}")
        return False


async def test_workaround_capability(provider_name: str, model: str, api_key: str, base_url: str):
    """测试替代方案：单帧 + Prompt描述尾帧"""
    print(f"\n[测试3] 替代方案（Prompt描述尾帧）- {provider_name}/{model}")

    provider = get_video_provider(provider_name)

    # 在prompt中详细描述尾帧状态
    enhanced_prompt = """
    A person transitioning from standing pose to sitting pose.
    Starting position: standing upright with arms at sides.
    Ending position: sitting on a chair with hands on knees.
    Smooth continuous motion, maintain anatomical consistency.
    """

    try:
        video_url = await provider.generate(
            image_url=START_FRAME,
            prompt=enhanced_prompt,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        print(f"  ✅ 替代方案可行")
        print(f"  输出：{video_url}")
        print(f"  ⚠️  注意：需要人工评估视频质量（是否真的过渡到尾帧状态）")
        return True
    except Exception as e:
        print(f"  ❌ 替代方案失败：{e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="API双帧能力验证")
    parser.add_argument("--provider", required=True, help="Provider名称：dashscope/minimax/runway")
    parser.add_argument("--model", required=True, help="模型名称：wanx2.1-i2v/wan2.6-i2v-flash")
    parser.add_argument("--api-key", default="", help="API密钥（如未提供则从环境变量读取）")
    parser.add_argument("--base-url", default="", help="API Base URL")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("API双帧能力验证测试")
    print("=" * 60)

    # 测试1：单帧I2V（基础能力）
    single_frame_ok = await test_single_frame_capability(
        args.provider, args.model, args.api_key, args.base_url
    )

    if not single_frame_ok:
        print("\n❌ API不支持单帧I2V，无法继续测试")
        return

    # 测试2：双帧输入（核心能力）
    dual_frame_ok = await test_dual_frame_capability(
        args.provider, args.model, args.api_key, args.base_url
    )

    # 测试3：替代方案
    workaround_ok = await test_workaround_capability(
        args.provider, args.model, args.api_key, args.base_url
    )

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"单帧I2V：{'✅ 支持' if single_frame_ok else '❌ 不支持'}")
    print(f"双帧输入：{'✅ 支持' if dual_frame_ok else '❌ 不支持'}")
    print(f"替代方案：{'✅ 可行' if workaround_ok else '❌ 不可行'}")

    if dual_frame_ok:
        print("\n🎉 结论：该API支持双帧输入，可以实施完整方案")
    elif workaround_ok:
        print("\n⚠️  结论：该API不支持双帧，但替代方案可行（质量可能降低）")
    else:
        print("\n❌ 结论：该API不适合过渡分镜方案，建议更换API或放弃过渡分镜")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 15.3 测试图片准备

需要准备两张测试图片（起始帧和结束帧）：

**脚本**：`tests/prepare_test_frames.py`

```python
"""
准备测试帧
从已有视频中提取起始帧和结束帧
"""

from app.services.ffmpeg import extract_last_frame
from app.services.image import generate_image
from pathlib import Path

TEST_DIR = Path("media/test_images")
TEST_DIR.mkdir(parents=True, exist_ok=True)


async def prepare_test_frames():
    """生成两张有明显差异的测试帧"""

    # 起始帧：站立姿势
    start_prompt = """
    A young woman standing in a modern office, wearing a blue blouse and black pants.
    Her arms are at her sides, facing the camera directly.
    Natural lighting from large windows, professional atmosphere.
    """

    # 结束帧：坐姿
    end_prompt = """
    A young woman sitting on an office chair, wearing a blue blouse and black pants.
    Her hands are resting on her knees, looking at the camera.
    Same modern office background with large windows.
    Natural lighting, professional atmosphere.
    """

    print("生成起始帧...")
    start_result = await generate_image(
        prompt=start_prompt,
        shot_id="test_start_frame",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key="YOUR_API_KEY",
        image_base_url="YOUR_BASE_URL",
    )
    print(f"起始帧已保存：{start_result['image_url']}")

    print("\n生成结束帧...")
    end_result = await generate_image(
        prompt=end_prompt,
        shot_id="test_end_frame",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key="YOUR_API_KEY",
        image_base_url="YOUR_BASE_URL",
    )
    print(f"结束帧已保存：{end_result['image_url']}")

    print("\n✅ 测试帧准备完成")


if __name__ == "__main__":
    import asyncio
    asyncio.run(prepare_test_frames())
```

---

### 15.4 执行测试

```bash
# 1. 准备测试图片
python tests/prepare_test_frames.py

# 2. 测试 Dashscope (阿里云)
python tests/api_capability_test.py \
  --provider dashscope \
  --model wanx2.1-i2v \
  --api-key $DASHSCOPE_API_KEY

# 3. 测试 Runway
python tests/api_capability_test.py \
  --provider runway \
  --model gen3-turbo \
  --api-key $RUNWAY_API_KEY

# 4. 测试 Minimax
python tests/api_capability_test.py \
  --provider minimax \
  --model video-01 \
  --api-key $MINIMAX_API_KEY
```

---

### 15.5 人工质量评估

即使API支持双帧输入，也需要人工评估生成视频的质量：

**评估维度**：
1. **物理连贯性**：动作是否自然（无肢体扭曲、穿模）
2. **首尾一致性**：首帧和尾帧是否与输入图片匹配
3. **过渡平滑度**：中间过渡是否流畅（无突然跳变）
4. **画质稳定性**：全程画质是否一致（无闪烁、模糊）

**评估脚本**：`tests/evaluate_transition_quality.py`

```python
"""
人工质量评估辅助脚本
将生成的视频下载到本地，方便逐帧查看
"""

import httpx
from pathlib import Path

OUTPUT_DIR = Path("media/test_outputs")


async def download_video_for_review(video_url: str, shot_id: str):
    """下载视频到本地供人工审查"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(video_url)
        resp.raise_for_status()

        output = OUTPUT_DIR / f"{shot_id}_review.mp4"
        output.write_bytes(resp.content)
        print(f"已下载：{output}")
        print(f"请用视频播放器逐帧查看：vlc {output}")


# 用法
async def main():
    # 替换为实际生成的视频URL
    video_url = "https://xxx.oss-cn-shanghai.aliyuncs.com/xxx.mp4"
    await download_video_for_review(video_url, "test_dual_frame")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

### 15.6 测试报告模板

```markdown
# API双帧能力测试报告

**测试日期**：2026-03-XX
**测试人**：XXX
**API Provider**：Dashscope
**模型**：wanx2.1-i2v

## 测试结果

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 单帧I2V | ✅ | 基础能力正常 |
| 双帧输入 | ❌ | 接口不支持 end_frame_url 参数 |
| 替代方案（Prompt） | ⚠️ | 可生成视频，但尾帧状态不准确 |

## 质量评估

**视频1（单帧 + Prompt描述）**：
- 物理连贯性：3/5（轻微肢体扭曲）
- 首尾一致性：2/5（尾帧与目标姿势不符）
- 过渡平滑度：4/5（过渡较流畅）
- 画质稳定性：4/5（无明显闪烁）

**结论**：
该API不支持双帧输入，替代方案质量不达标（尾帧一致性差）。
建议：
1. 尝试其他API（Runway/Minimax）
2. 或者改用视频插帧后处理方案（RIFE）

---

**下一步行动**：
- [ ] 测试 Runway Gen-3
- [ ] 测试 Minimax video-01
- [ ] 评估 RIFE 插帧方案
```

---

### 15.7 快速决策流程

```
测试 API 双帧能力
  ├─ ✅ 支持 → 进入 Phase 1（实施最小方案）
  └─ ❌ 不支持
      ├─ 测试替代方案（Prompt描述尾帧）
      │   ├─ ✅ 质量达标 → 采用替代方案
      │   └─ ❌ 质量不达标
      │       ├─ 测试其他API
      │       └─ 评估视频插帧方案（RIFE）
      │           ├─ ✅ 可行 → 后处理方案
      │           └─ ❌ 不可行 → 放弃过渡分镜
```

**建议**：先完成 API 能力验证，再决定是否投入开发资源。
