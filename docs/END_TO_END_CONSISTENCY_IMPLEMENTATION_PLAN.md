# 全流程一致性实施计划

> 更新日期：2026-03-30
>
> 文档定位：基于当前仓库实际代码、测试、README 与已落地接口，重新整理“全流程一致性”现状、缺口、优先级与实施顺序。
>
> 使用原则：本文件只写当前已实现事实与明确计划，不把未来项写成现状；若与旧设计文档冲突，以代码和当前接口行为为准。

---

## 1. 这份文档要解决什么

当前项目的一致性能力已经不再是“设计稿阶段”:

1. `StoryContext` 已经成为图片/视频主链路的运行期一致性入口。
2. `prepare_story_context()` 已经承担“按需补齐结构化缓存”的职责。
3. Scene Reference、手动分镜、自动流水线、transition、拼接、恢复都已经接入同一套大方向。

但仓库里仍然同时存在：

1. 文档描述偏旧。
2. 个别入口仍保留 fallback / legacy path。
3. `storyboard_generation` 与 `pipeline.generated_files` 的边界容易被误解。
4. `character_appearance_cache`、`scene_style_cache`、`visual_dna` 仍处于“统一中但未完全收口”的过渡态。

这份文档的目标，是把下面四件事说清楚：

1. 当前项目真实已经落地了什么。
2. 哪些描述在旧文档里已经落后或不统一。
3. 接下来应该按什么顺序继续收口。
4. 哪些边界必须保持，不能在后续改造时被破坏。

---

## 2. 当前项目的真实一致性主链路

### 2.1 运行主线

当前实际主线如下：

```text
Story / selected_setting / characters / art_style
  -> prepare_story_context()
  -> parse_script_to_storyboard()
  -> Scene Reference assets
  -> build_generation_payload()
  -> image / video / transition
  -> concat
  -> storyboard_generation 恢复态 + pipeline.generated_files 运行态
```

### 2.2 已经落地的核心能力

#### A. `StoryContext` 已是运行期主入口

- 代码落点：`app/core/story_context.py`
- 当前 `build_generation_payload()` 会统一生成：
  - `image_prompt`
  - `final_video_prompt`
  - `negative_prompt`
  - `reference_images`
  - `source_scene_key`
- 手动批量图、手动批量视频、单镜头图、单镜头视频、transition 生成前的 prompt 组装，已经都围绕这套能力展开。

#### B. `prepare_story_context()` 已经负责“按需准备缓存”

- 代码落点：`app/services/story_context_service.py`
- 当前在有可用 LLM 凭证时，会按需补齐：
  - `meta.character_appearance_cache`
  - `meta.scene_style_cache`
- `character_appearance_cache` 当前抽取字段是：
  - `body`
  - `clothing`
  - `negative_prompt`
- `scene_style_cache` 当前抽取字段是：
  - `keywords`
  - `image_extra`
  - `video_extra`
  - `negative_prompt`
- 这些缓存缺失时才会补；不是每次都重算。

#### C. Scene Reference 已进入图片主链路

- 代码落点：`app/services/scene_reference.py`、`app/routers/story.py`
- 当前按“每集环境组”生成共享环境图，而不是按单场景重复生成。
- 结果会写入：
  - `meta.episode_reference_assets`
  - `meta.scene_reference_assets`
- 分镜 Shot 会带 `source_scene_key`。
- 运行期图片参考会优先组合：
  - 角色设定图
  - 命中的场景环境图

#### D. 图片与视频都已经区分正向 prompt 和 negative prompt

- 图片服务：`app/services/image.py`
  - 支持 `negative_prompt`
  - 支持 `reference_images`
  - 若 provider 因 `negative_prompt` 或 `reference_images` 返回 400/422，会自动降级重试
- 视频服务：`app/services/video.py`
  - 主镜头视频支持单首帧 I2V
  - `negative_prompt` 已作为参数保留并传入 provider
  - 双帧只对支持双帧的 provider 开放

#### E. 主镜头与 transition 的边界已经明确

- 普通主镜头统一走单首帧 I2V。
- `last_frame_prompt / last_frame_url` 已从主镜头主链路退出，只保留兼容痕迹。
- transition 只允许相邻镜头。
- transition 必须建立在已有主镜头视频之上。
- transition 的首尾锚点优先从相邻主镜头视频抽帧；抽帧失败时会回退到已有静态分镜图。

#### F. 手动页、单资产接口、自动流水线都已经具备状态持久化

- 手动分镜与单资产接口会同时写入：
  - `story.meta.storyboard_generation`
  - `pipeline.generated_files`
- 自动 `auto-generate` 当前仍以 `pipeline` 为主要运行态真相源。
- `storyboard_generation` 当前不仅保存恢复态，也会镜像部分 `generated_files`、`shots`、`pipeline_id`、`final_video_url`。

#### G. 当前已有测试保护

一致性相关测试已存在，不是纯文档设计态：

- `tests/test_story_context.py`
- `tests/test_story_router.py`
- `tests/test_pipeline_runtime.py`
- `tests/test_scene_reference.py`
- `tests/test_storyboard_state.py`
- `tests/test_image_reference_security.py`
- `tests/test_image_service_retry.py`
- `tests/test_story_identity.py`
- `tests/test_story_context_anchor_boundaries.py`

---

## 3. 当前文档里需要统一修正的点

这部分专门列出“旧说法容易误导开发”的地方。

### 3.1 `storyboard_generation` 不能再只写成“纯手动恢复态”

当前真实情况是：

1. 它确实服务于手动分镜页恢复。
2. 但它也会同步镜像 `generated_files`。
3. 它还会把 `tts / images / videos` 结果反写回 `shots`，方便前端恢复。
4. `final_video_url` 也会写入这里。

因此更准确的口径应是：

- `pipeline.generated_files` 是运行态主真相源。
- `storyboard_generation` 是手动页恢复态，并镜像一部分运行资产，便于刷新和历史恢复。

### 3.2 `pipeline.generated_files` 仍然是运行期主真相源

当前 `generated_files` 可能包含：

1. `storyboard`
2. `tts`
3. `images`
4. `videos`
5. `transitions`
6. `timeline`
7. `final_video_url`
8. `meta`

transition 与 concat 更偏向读取 pipeline 当前真实资产，而不是只看前端临时状态。

### 3.3 `StoryContext` 已统一主方向，但并未完全去掉 fallback

当前仍存在过渡态路径：

1. `app/routers/image.py` 里仍保留 `_build_basic_payload()` 兜底。
2. `app/services/pipeline_executor.py` 里仍保留 `_build_generation_payload()` fallback 注释与兼容逻辑。
3. `build_story_context()` 仍会在缓存缺失时回退到：
   - `character_images.visual_dna`
   - `design_prompt`
   - `description`

因此当前更准确的表述应是：

- 主链路已经统一到 `StoryContext`。
- 但工程上仍保留有限 fallback，用于避免入口在异常时彻底失效。

### 3.4 `character_appearance_cache` 还不是绝对唯一来源

当前真实逻辑是：

1. 优先使用 `meta.character_appearance_cache`
2. 缺失时回退到 `character_images.visual_dna`
3. 再缺失时回退到 `design_prompt / description` 清洗结果

同时，`prepare_story_context()` 还会把抽取出的 `body` 投影回 `character_images.visual_dna`。

这说明项目现状不是“完全去掉 visual_dna”，而是：

- 正在把结构化缓存作为主消费源；
- 但 `visual_dna` 仍是兼容投影层。

### 3.5 `scene_style_cache` 也不是唯一风格来源

当前 `StoryContext` 的场景风格由两部分组成：

1. 基于 `genre` 的内置 `_GENRE_STYLE_RULES`
2. `meta.scene_style_cache` 的结构化抽取结果

所以当前不是“只有 scene_style_cache 在工作”，而是“genre 规则 + scene_style_cache 叠加”。

### 3.6 transition 的描述需要更精确

当前 transition 规则不是单纯“从相邻主镜头视频里抽帧”，而是：

1. 先要求相邻主镜头视频已经存在。
2. 再尝试从视频抽取：
   - 前镜最后一帧
   - 后镜第一帧
3. 若抽帧失败且有对应分镜图，则回退到分镜图。
4. 只允许支持双帧的 provider，目前代码口径默认要求 `doubao`。

---

## 4. 当前必须遵守的边界

后续所有一致性改造，都应继续遵守这些边界。

### 4.1 `StoryContext` 继续作为运行期统一入口

- 不再新建“第五套 prompt 中心”。
- 新能力优先挂在：
  - `prepare_story_context()`
  - `build_generation_payload()`

### 4.2 普通主镜头继续保持单首帧 I2V

- 不把双帧逻辑重新引回主镜头。
- `last_frame_prompt / last_frame_url` 不再回流主链路。
- 双帧只留给 transition。

### 4.3 文本风格缓存与图像参考资产分开治理

- `scene_style_cache` 是文本风格锚点。
- `episode_reference_assets / scene_reference_assets` 是图像参考资产。
- 两类都能影响运行期，但职责不同，不能混写成一个缓存。

### 4.4 provider 不支持时优先“丢弃参数”而不是污染正向 prompt

- 图片 provider 拒绝 `negative_prompt` 时，去掉它再试。
- 图片 provider 拒绝 `reference_images` 时，去掉它再试。
- 不应把“不要出现什么”反向塞回正向 prose。

### 4.5 状态边界继续保持“双层”

- `pipeline.generated_files` 继续作为运行期主真相源。
- `story.meta.storyboard_generation` 继续作为手动恢复态和镜像层。
- 后续可以继续收口，但不要重新退回“只有前端内存态”。

### 4.6 文档不得把未来项写成现状

以下能力当前仍未进入正式主链路：

- DSPy 运行时代码
- Judge / Review / Shadow mode
- Feedback Loop 自动重试闭环
- 独立数字资产库
- transition 删除接口

---

## 5. 当前推荐目标态

在现有仓库基础上，推荐继续沿当前骨架增量收口，而不是重做架构。

### 5.1 目标结构

```text
Story data
  -> prepare_story_context()
  -> storyboard / scene reference
  -> build_generation_payload()
  -> image / video / transition / concat
  -> pipeline.generated_files
  -> storyboard_generation restore mirror
```

### 5.2 一致性能力分层

#### 第一层：结构化与资产层

- `character_appearance_cache`
- `scene_style_cache`
- `character_images`
- `episode_reference_assets`
- `scene_reference_assets`

#### 第二层：运行期组装层

- `prepare_story_context()`
- `build_story_context()`
- `build_generation_payload()`

#### 第三层：执行层

- storyboard
- tts
- image
- video
- transition
- concat

#### 第四层：恢复与状态层

- `pipeline.generated_files`
- `story.meta.storyboard_generation`

#### 第五层：未来增强层

- 更严格 schema 与版本化
- DSPy 离线优化
- Judge / Feedback Loop

当前优先级应该是先把前四层收稳，再考虑第五层。

---

## 6. 分阶段实施顺序

### Phase 1：先把运行期契约和文档口径收口

#### 当前状态

已部分完成，但还没彻底统一。

已经有的基础：

1. `build_generation_payload()` 已是主入口。
2. 图片/视频/transition 都已消费其结果或围绕其结果组装。
3. 主镜头单首帧 I2V 与 transition 双帧边界已明确。
4. `negative_prompt` 与 `reference_images` 已进入运行期。

仍然存在的问题：

1. 旧文档对 `storyboard_generation` 与 `generated_files` 的职责写得过粗。
2. 个别入口仍保留 fallback builder。
3. auto / manual / single asset / transition 的统一口径还没有完全钉死。

#### 本阶段目标

把“现有已经能跑的事实”统一成稳定契约，而不是继续容忍多种说法并存。

#### 本阶段要做什么

1. 统一文档中对 `StoryContext`、`storyboard_generation`、`pipeline.generated_files` 的描述。
2. 统一 transition 的真实规则描述。
3. 标记哪些 fallback 仍保留，哪些不应再扩散。
4. 明确 auto 与 manual 的状态真相源边界。

#### 完成标准

1. 新文档不再把过渡态写成终态。
2. 所有主要文档对状态边界描述一致。
3. 后续开发者不会再误以为 `storyboard_generation` 是唯一真相源。

### Phase 2：继续压缩 fallback / legacy path

#### 当前状态

处于过渡态。

当前仍保留：

1. `_build_basic_payload()` 兜底逻辑
2. PipelineExecutor 内部 fallback payload
3. `visual_dna` 投影与兼容消费

#### 本阶段目标

在不破坏可用性的前提下，逐步让更多入口只走 `StoryContext` 主链路。

#### 本阶段要做什么

1. 盘点哪些 fallback 只是临时保底，哪些已经变成事实依赖。
2. 把能删掉的 legacy builder 收掉。
3. 把保留的兜底逻辑限定在极小范围，并补测试。

#### 完成标准

1. 主入口不再偷偷拼装私有 prompt。
2. 兜底逻辑只在异常场景生效。
3. 文档能清楚标出剩余兼容层。

### Phase 3：把结构化缓存契约做硬

#### 当前状态

已经可用，但仍偏宽松。

现状：

1. `character_appearance_cache` 已稳定消费 `body / clothing / negative_prompt`
2. `scene_style_cache` 已稳定消费 `keywords / image_extra / video_extra / negative_prompt`
3. 当前没有统一 schema version 与来源元数据

#### 本阶段目标

让缓存从“可用”升级为“可演进、可校验、可回滚”。

#### 本阶段要做什么

1. 为 appearance/style cache 定义正式 schema 版本字段。
2. 标准化来源标记，例如：
   - llm provider
   - model
   - updated_at
3. 明确提取失败时不得污染已有可用缓存。
4. 明确 `visual_dna` 的最终角色：保留兼容投影还是逐步退役。

#### 完成标准

1. 文档、代码、测试对缓存字段口径一致。
2. 缓存写入失败不会破坏现有稳定结果。
3. 结构化缓存成为更明确的主数据源。

### Phase 4：做全入口一致性验收

#### 当前状态

主方向正确，但仍需要“跨入口”确认。

需要一起看的入口：

1. `auto-generate`
2. 手动 `storyboard -> generate-assets -> render-video`
3. 单镜头 `tts / image / video`
4. `transitions/generate`
5. `concat`
6. History 恢复

#### 本阶段目标

确认这些入口在同一故事、同一分镜、同一恢复场景下，表现符合统一预期。

#### 本阶段要做什么

1. 核对相同 Shot 在不同入口下是否得到相同 prompt 组装。
2. 核对状态写回是否都能正确恢复。
3. 核对 transition 是否始终基于 pipeline 当前真实视频资产。
4. 核对刷新、历史恢复、重新生成是否会出现状态分叉。

#### 完成标准

1. auto / manual / single asset / transition 的行为可解释。
2. 恢复逻辑不再依赖前端临时状态。
3. 文档与测试都能覆盖这些边界。

### Phase 5：最后才考虑 DSPy 与 Feedback Loop

#### 当前状态

都未正式开始。

#### 当前不能误写成已支持的内容

1. DSPy compile / optimizer 流程
2. Judge / review_required
3. shadow mode
4. 局部自动重试闭环

#### 推荐方向

1. DSPy 只用于离线优化结构化提取器，不改运行期主入口。
2. Feedback Loop 只作为可关闭增强层，不得变成新的 prompt 主中心。

#### 完成标准

1. 关闭增强层时，当前主链路行为完全不变。
2. 打开增强层时，只影响局部，不破坏恢复性。

---

## 7. 统一数据口径

### 7.1 Story 侧核心字段

当前应继续视为一致性核心数据的字段：

1. `stories.characters`
2. `stories.character_images`
3. `stories.selected_setting`
4. `stories.art_style`
5. `stories.meta.character_appearance_cache`
6. `stories.meta.scene_style_cache`
7. `stories.meta.episode_reference_assets`
8. `stories.meta.scene_reference_assets`
9. `stories.meta.storyboard_generation`

### 7.2 Pipeline 侧核心字段

当前应继续把 `pipelines.generated_files` 视为运行期主真相源，重点包括：

1. `storyboard`
2. `tts`
3. `images`
4. `videos`
5. `transitions`
6. `timeline`
7. `final_video_url`
8. `meta`

### 7.3 Shot 运行期关键字段

当前主链路稳定依赖的字段包括：

1. `shot_id`
2. `image_prompt`
3. `final_video_prompt`
4. `negative_prompt`
5. `reference_images`
6. `source_scene_key`
7. `image_url`
8. `video_url`
9. `audio_url`
10. `audio_duration`

下列字段当前不应被写成已进入正式主链路：

1. `review_required`
2. `feedback_*`
3. 新的多级 judge 字段

---

## 8. 推荐验收方式

后续每推进一个阶段，建议都按下面顺序验收。

### 8.1 先看入口是否继续统一

- 是否继续围绕 `prepare_story_context()` 与 `build_generation_payload()`
- 是否又长出新的私有 prompt builder

### 8.2 再看状态边界是否仍然清晰

- `pipeline.generated_files` 是否仍是运行期主真相源
- `storyboard_generation` 是否仍是恢复态镜像层

### 8.3 再看全入口行为

- auto
- manual
- single asset
- transition
- concat
- restore

### 8.4 最后看测试

当前建议的最小验证基线：

```bash
uv run python -m unittest discover -s tests -q
node --test frontend/src/utils/storyChat.test.js frontend/src/utils/storyChat.multiline-sections.test.js frontend/src/utils/storyChat.numbering.test.js
npm --prefix frontend run build
```

---

## 9. 最终结论

对当前项目来说，最稳妥的路线不是推倒重来，而是继续沿着现有主线增量收口：

1. 先统一文档口径和运行期契约。
2. 再压缩 fallback / legacy path。
3. 再把结构化缓存契约做硬。
4. 再做全入口一致性验收。
5. 最后才考虑 DSPy 和 Feedback Loop。

这条路线的价值在于：

1. 不会破坏当前已经跑通的主链路。
2. 能准确反映仓库今天真实状态。
3. 能让后续开发建立在现有代码与测试之上，而不是建立在过时描述上。
