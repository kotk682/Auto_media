# 主流程接入过渡分镜说明

> 目标：把“过渡分镜”真正接进当前自动生成主流程，而不是只停留在设计文档里。
> 当前确认方案：第一版采用“手动确认生成过渡视频”，不是让 LLM 在 storyboard 阶段直接输出全部过渡分镜。
> 适用范围：`PipelineExecutor` 主流程、链式/普通视频生成、前端交互、过渡视频接口。
> 推荐首期范围：仅在 `doubao` provider 下完整启用双帧过渡；其他 provider 先兼容字段、允许降级。

---

## 1. 当前主流程现状

当前自动主流程入口在 `app/services/pipeline_executor.py`：

- `separated`
  - 分镜 -> TTS -> 生图 -> 图生视频 -> FFmpeg 合成
- `integrated`
  - 分镜 -> 生图 -> 视频生成
- `chained`
  - 分镜 -> TTS -> 场景内链式生成
  - 同场景内：上一镜头视频最后一帧，作为下一镜头首帧参考

当前已经具备两块基础能力：

1. `Shot` 已支持：
   - `image_prompt`
   - `final_video_prompt`
   - `last_frame_prompt`
   - `last_frame_url`
2. Doubao provider 已支持首尾帧双帧视频生成：
   - `first_frame`
   - `last_frame`

但现在还没有真正落地“手动确认式过渡视频”这件事：

- 前端没有在两个相邻镜头之间提供“生成过渡视频”按钮
- 后端没有独立的“过渡视频生成”接口
- 主流程结果里没有“主镜头 + 手动补充过渡视频”的统一顺序管理
- 过渡视频还没有被视为一种运行时新增资产

一句话说，当前系统只有“镜头连续性增强”，还没有“用户确认后插入过渡片段”的主流程能力。

---

## 2. 目标效果

接入后，主流程默认仍然只生成主镜头：

```text
scene1_shot1 -> scene1_shot2 -> scene1_shot3
scene2_shot1 -> scene2_shot2 -> scene2_shot3
```

当相邻两个主镜头都已经完成视频生成后，前端在它们中间显示一个按钮：

```text
[scene1_shot1]
   ↓
[生成过渡视频]
   ↓
[scene1_shot2]
```

用户点击后，系统为这一对相邻镜头生成一个运行时过渡片段，最终播放顺序变成：

```text
scene1_shot1 -> transition(scene1_shot1, scene1_shot2) -> scene1_shot2
```

其中：

- 主镜头仍来自原 storyboard
- 过渡视频不是 storyboard 固定输出，而是用户在 UI 中手动确认后新增的运行时片段
- 过渡视频只存在于两个相邻主镜头之间

---

## 3. 推荐接入策略

不要一开始就改成“LLM 自动产出过渡分镜”。推荐先做手动确认版。

### Phase 1

做“手动确认生成过渡视频”：

原因：

- 不改 storyboard 主结构，风险最低
- 用户可以只在必要的位置生成过渡，不会把片段数量炸开
- 更适合人工判断“哪里真的需要过渡”
- 最容易接入 Doubao 的双帧能力

### Phase 2

如果手动版稳定，再增加“自动推荐哪些位置适合生成过渡视频”。

### Phase 3

最后再考虑让 LLM 在 storyboard 中直接输出过渡分镜。

---

## 4. 主流程应该怎么改

### 4.1 分镜层：第一版不要强依赖 LLM 输出过渡分镜

第一版建议保持 storyboard 基本不变：

- 仍然只生成主镜头
- 不要求 LLM 输出 `scene*_trans*`
- 不要求 `Shot` 里立即加入完整过渡分镜 schema

原因：

- 这次的目标是“主流程中人工确认补过渡”
- 不是“重做一版自动过渡 storyboard”
- 先把运行时资产链路打通，比先改 LLM prompt 更重要

第一版最多只需要增加一个轻量的运行时结构，例如：

```python
class TransitionRequest(BaseModel):
    from_shot_id: str
    to_shot_id: str
    transition_prompt: Optional[str] = None
```

这里的 `transition_prompt` 可以先由系统自动生成，也可以允许前端人工微调。

---

### 4.2 执行层：主流程要支持“相邻镜头生成完成后，补一个过渡视频”

需要修改：

- `app/services/pipeline_executor.py`
- `app/services/video.py`
- `app/routers/pipeline.py`
- `frontend/src/views/VideoGeneration.vue`

当前主流程的问题不是“不会自动拆主镜和过渡镜”，而是“生成完成后没有补一个过渡片段的入口”。

所以第一版建议这样做：

#### Step A：主流程照旧生成主镜头

- 仍然按原 storyboard 生成主镜头图片和视频
- 不改变现有 `separated` / `integrated` / `chained` 的主逻辑

#### Step B：当两个相邻主镜头都具备 `video_url` 时，在 UI 中间显示按钮

按钮出现条件：

- 两个镜头在 storyboard 顺序上相邻
- 前一个镜头已有 `video_url`
- 后一个镜头已有 `video_url`
- 当前这对镜头之间还没有过渡视频

按钮位置：

- 渲染在两个 shot card 之间
- 文案建议为 `生成过渡视频`

#### Step C：点击按钮后，请求后端生成过渡视频

后端应接收：

- `from_shot_id`
- `to_shot_id`
- `from_video_url`
- `to_image_url` 或 `to_video_url`
- 可选 `transition_prompt`

目的：

- 让过渡视频成为一种独立、可追加、可重试的资产
- 不影响已生成好的主镜头
- 失败时只重试这一个过渡，不重跑整条流水线

#### Step D：生成完成后，将过渡视频插入播放顺序

可以在运行时结果中记录为：

```python
{
    "transition_id": "transition_scene1_shot1__scene1_shot2",
    "from_shot_id": "scene1_shot1",
    "to_shot_id": "scene1_shot2",
    "video_url": "/media/videos/transition_scene1_shot1__scene1_shot2.mp4"
}
```

前端展示时，将它插入两个 shot 中间。

---

### 4.3 视频层：新增“过渡视频生成”能力，不要先重构整条链式流程

需要修改：

- `app/services/video.py`
- `app/services/ffmpeg.py`

第一版最稳的做法不是改 `generate_videos_chained()` 本体，而是增加一个新的方法，例如：

```python
async def generate_transition_video(
    from_video_path: str,
    to_image_url: str,
    transition_id: str,
    prompt: str,
    ...
) -> dict:
    ...
```

推荐生成方式：

1. 从前一个镜头视频提取最后一帧
2. 取后一个镜头的首帧图作为目标尾帧
3. 如果 provider 支持双帧：
   - 首帧 = 前镜尾帧
   - 尾帧 = 后镜首帧
4. 如果 provider 不支持双帧：
   - 退化成以前镜尾帧为首帧的单帧 I2V
   - prompt 中增加“过渡到下一个构图”的提示

如果后续验证效果很好，再考虑把它并回 `generate_videos_chained()`。

---

### 4.4 Provider 层：首期只对 Doubao 真正启用双帧过渡

当前 provider 情况：

- `doubao`
  - 已支持 `last_frame_url`
- `dashscope`
  - 仅接口兼容，实际忽略
- `kling`
  - 仅接口兼容，实际忽略
- `minimax`
  - 仅接口兼容，实际忽略

所以这条“手动确认生成过渡视频”的链路，建议这样处理：

- 如果 `video_provider == "doubao"`：
  - 过渡视频使用双帧模式
- 否则：
  - 降级为单帧 I2V
  - 仍可使用 transition prompt
  - 但不要承诺精确的起止姿态

也就是说，主流程里要显式写清楚：

```python
supports_dual_frame = video_provider == "doubao"
```

然后按 provider 决定是否传 `last_frame_url`。

---

## 5. 手动确认版过渡视频的主流程时序

推荐主流程时序如下：

```text
Step 1: LLM 生成普通 storyboard
Step 2: 主流程生成主镜头图片和视频
Step 3: 前端检查相邻镜头是否都已有 video_url
Step 4: 在合适位置显示“生成过渡视频”按钮
Step 5: 用户点击按钮，提交 transition generate 请求
Step 6: 后端提取前镜尾帧，并读取后镜首帧
Step 7: 调用 provider 生成过渡视频
Step 8: 将 transition asset 插入两个镜头之间展示与拼接
```

---

## 6. 前端和接口需要配合的点

需要关注：

- `frontend/src/views/VideoGeneration.vue`
- `app/schemas/pipeline.py`

建议增加的前端行为：

1. 在两个相邻 shot card 之间渲染插槽
   - 如果两边都已有 `video_url` 且尚未生成过渡视频，显示按钮
   - 按钮文案：`生成过渡视频`

2. 点击按钮后的请求参数
   - `from_shot_id`
   - `to_shot_id`
   - 可选 `transition_prompt`

3. 成功后前端保存 transition 结果
   - `transition_id`
   - `from_shot_id`
   - `to_shot_id`
   - `video_url`

4. 结果排序
   - 必须按 storyboard 原顺序展示和拼接
   - transition 结果展示在 `from_shot` 和 `to_shot` 之间

5. 重试能力
   - 单个过渡视频失败时，可单独重试
   - 不影响已有主镜头

---

## 7. 建议的数据样例

```json
{
  "transition_id": "transition_scene1_shot1__scene1_shot2",
  "from_shot_id": "scene1_shot1",
  "to_shot_id": "scene1_shot2",
  "prompt": "Smoothly transition from the previous ending pose into the next framing, keeping identity, clothing, and lighting consistent.",
  "video_url": "/media/videos/transition_scene1_shot1__scene1_shot2.mp4"
}
```

---

## 8. 第一阶段最小实现清单

如果只做“能跑起来的第一版”，建议只做下面这些：

1. 前端在两个相邻镜头之间显示“生成过渡视频”按钮
2. 后端新增独立的 transition generate 接口
3. `video.py` 增加 `generate_transition_video()` 方法
4. `ffmpeg.py` 增加“提取前镜尾帧”复用逻辑
5. 仅在 `doubao` 下为过渡视频传 `last_frame_url`
6. 前端把 transition 结果插入两个镜头之间展示
7. 过渡视频支持单独重试和删除

这 7 项做完，就已经是可交互、可验证、风险较低的主流程版本。

---

## 9. 验收标准

接入完成后，至少满足下面几个标准：

1. storyboard 仍能稳定输出原有主镜头，不因过渡能力接入而被破坏
2. 相邻两个主镜头都生成完成后，前端能在中间显示按钮
3. 点击按钮后，后端能基于前镜尾帧和后镜首帧生成过渡视频
4. `doubao` 下过渡视频可以走双帧模式
5. 非 Doubao provider 不会报错，只会降级
6. 最终拼接顺序与 storyboard 顺序完全一致，并正确插入过渡片段
7. 过渡视频失败时只影响当前按钮对应的片段，不影响主流程已有结果

---

## 10. 明确不建议的做法

以下做法不建议直接进入主流程：

- 第一版就强依赖 LLM 自动产出完整过渡分镜
- 先做跨场景桥接，再补相邻镜头过渡
- 在 `separated`、`integrated`、`chained` 三条策略里同时大改
- 把过渡 prompt 写成和主镜头一样长的大段描述
- 不区分 provider，盲目给所有平台传 `last_frame_url`

这些都会让系统复杂度暴涨，但质量不一定提升。

---

## 11. 推荐结论

如果要把过渡分镜接进主流程，最稳的实施路径是：

- 第一版先不改 storyboard 主结构
- 先做“相邻镜头生成完成后，手动确认生成过渡视频”的交互
- 后端用“前镜尾帧 + 后镜首帧”生成过渡片段
- 首期只对 Doubao 打开双帧过渡
- 其他 provider 全部按降级逻辑兼容

这样改动范围清晰、收益直接，也最符合当前代码结构。
