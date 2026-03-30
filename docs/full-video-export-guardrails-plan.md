# 完整视频导出防串片改造说明

## 目标

解决两个问题：

1. 当前重新解析分镜时，如果这次只解析了部分场景，历史 `generated_files` 里的旧图片、旧视频、旧 transition 仍可能被继续复用。
2. “导出完整视频”现在只要能收集到一批 `video_url` 就会发起拼接，没有校验“当前这版分镜”的主镜头和过渡镜头是否全部生成完成。

期望结果：

1. 完整视频导出只允许使用“当前 storyboard 对应的素材”。
2. 导出前必须满足：
   - 当前 storyboard 的核心分镜全部有主视频
   - 当前 storyboard 的相邻分镜过渡视频全部生成
3. 如果只解析了部分场景，旧场景素材不能混入这次导出。

## 当前问题定位

### 1. 历史素材会被持续 merge

当前以下位置都采用“增量 merge”思路：

- `app/services/storyboard_state.py`
  - `_merge_generated_files`
  - `build_storyboard_generation_state`
- `app/routers/pipeline.py`
  - `_merge_generated_files`
  - `_persist_manual_pipeline_state`

这会导致新的 `generated_files` 写入时，旧的 `tts/images/videos/transitions/timeline/final_video_url` 默认被保留。

如果这次解析出来的 `shots` 变少了，或者只覆盖部分场景，但旧素材对应的 `shot_id / transition_id` 还留在状态里，它们后面仍可能被读取到。

### 2. 前端导出只做“收集 URL”，不做完整性校验

当前导出逻辑在 `frontend/src/views/VideoGeneration.vue` 的 `concatAllVideos()`：

1. 优先读取 `transitionTimeline`
2. 否则读取当前 `storyboardFlowItems`
3. 只要 `orderedVideoUrls.length > 0` 就调用 `/api/v1/pipeline/{project_id}/concat`

这里没有判断：

- 当前 storyboard 的每个核心分镜是否都有主视频
- 当前 storyboard 的每个相邻 transition 是否都有过渡视频
- `transitionTimeline` 是否只包含当前这版 storyboard 的条目

### 3. 后端 concat 接口也没有做“当前 storyboard 完整性”校验

当前 `app/routers/pipeline.py` 的 `concat_videos()` 只校验：

- `req.video_urls` 非空
- URL 是可信本地媒体路径

它不会校验：

- 这些 URL 是否对应当前 storyboard
- 当前 storyboard 是否已全部生成完毕
- 是否混入了旧 transition / 旧 shot 视频

## 建议改造方案

## 一、把“当前 storyboard”设为唯一真源

建议以当前 `storyboard_generation.shots` 作为导出唯一真源，动态推导：

- 当前有效 `shot_ids`
- 当前应存在的 `transition_ids`
- 当前完整导出的标准顺序

建议新增几个辅助函数，放在 `app/routers/pipeline.py` 或 `app/services/storyboard_state.py`：

- `_collect_storyboard_shot_ids(shots) -> list[str]`
- `_collect_expected_transition_ids(shots) -> list[str]`
- `_prune_generated_files_to_storyboard(generated_files, shots) -> dict`
- `_validate_export_readiness(shots, videos_map, transitions_map) -> dict`

其中：

- 核心分镜：当前 `shots` 列表中的每一个 `shot_id`
- 过渡分镜：当前 `shots` 中每一对相邻镜头形成的 `transition_{from}__{to}`

如果当前只有 1 个 shot，则不需要 transition。

## 二、重新解析 storyboard 时清理旧素材

建议在 `generate_storyboard()` 成功后，不再沿用旧的 story-level `generated_files`，而是显式重置为只保留当前 storyboard：

建议效果：

- 清空旧 `tts`
- 清空旧 `images`
- 清空旧 `videos`
- 清空旧 `transitions`
- 清空旧 `timeline`
- 清空旧 `final_video_url`
- 只保留新的 `generated_files.storyboard`

推荐做法有两种，优先选 A：

### 做法 A：给 storyboard state 增加 replace/prune 能力

在 `app/services/storyboard_state.py` 增加类似参数：

- `replace_generated_files: bool = False`
- 或 `prune_to_shots: bool = False`

在 `generate_storyboard()` 调用 `persist_storyboard_generation_state(...)` 时启用它。

这样新 storyboard 写入后，story meta 中只保留这次解析对应的资产空间。

### 做法 B：在生成 storyboard 后手工构造干净状态

直接在 `generate_storyboard()` 写入：

- `shots`
- `usage`
- `pipeline_id`
- `project_id`
- `story_id`
- `generated_files = {"storyboard": {...}}`
- `final_video_url = ""`

不沿用旧的 `generated_files` merge。

## 三、所有 generated_files 在持久化时按当前 shot 集裁剪

无论是单镜头接口还是批量接口，建议在落库前统一裁剪：

- `tts/images/videos` 只保留当前 `shot_ids`
- `transitions` 只保留当前相邻镜头的 transition
- `timeline` 只保留当前 storyboard 可推导出的时间线

推荐修改点：

- `app/services/storyboard_state.py`
  - `build_storyboard_generation_state`
  - `_apply_generated_files_to_shots`
- `app/routers/pipeline.py`
  - `_persist_manual_pipeline_state`

重点不是“追加更多 merge 规则”，而是“每次落库时先知道当前 storyboard 的合法边界，再裁剪非法旧条目”。

## 四、导出前必须做完整性校验

建议把“是否允许导出”定义成统一规则：

### 可导出条件

1. 当前 storyboard 至少有 1 个核心分镜
2. 每个核心分镜都存在 `video_url`
3. 如果核心分镜数量大于 1，则每一对相邻分镜都存在对应的 transition `video_url`
4. `timeline` 必须和当前 storyboard 一一对应
5. `final_video_url` 不能作为“允许再次导出”的依据，它只是上一次结果，不代表本次素材完整

### 不可导出场景

- 少任意一个核心分镜视频
- 少任意一个相邻 transition 视频
- `timeline` 中出现不属于当前 storyboard 的旧 transition
- 当前 storyboard 已变化，但 `generated_files` 仍保留上一次解析结果

## 五、把导出顺序放到后端生成，不再完全信任前端 URL 列表

推荐升级 `concat_videos()`：

1. 当提供 `pipeline_id` 时，后端自行读取当前 pipeline/storyboard 状态
2. 后端根据当前 `shots` 生成预期顺序：
   - `shot-1`
   - `transition_shot-1__shot-2`
   - `shot-2`
   - `transition_shot-2__shot-3`
   - `shot-3`
3. 校验全部素材齐全后，再拼出最终 `orderedVideoUrls`
4. 忽略或弱化前端传入的 `req.video_urls`

这样可以避免两类问题：

1. 前端误把旧素材 URL 带进来
2. 用户刷新后本地状态滞后，仍能导出错误顺序

如果要保持兼容，可以这样处理：

- 旧模式：无 `pipeline_id` 时沿用 `req.video_urls`
- 新模式：有 `pipeline_id` 时以后端推导顺序为准

## 六、前端按钮也要同步禁用

建议在 `frontend/src/views/VideoGeneration.vue` 增加一个 `exportReadiness` 计算属性，统一返回：

- `ready: boolean`
- `missingShotVideos: string[]`
- `missingTransitions: string[]`
- `message: string`

逻辑建议：

1. 从当前 `shots` 推导 `expectedTransitions`
2. 用当前 `transitionResults` 和 `shots[*].video_url` 校验完整性
3. 不满足时：
   - 禁用“导出完整视频”按钮
   - 在按钮旁展示明确原因

建议提示文案：

- `还有 2 个核心分镜未生成视频：scene1_shot2、scene1_shot3`
- `还有 1 个过渡分镜未生成：transition_scene1_shot2__scene1_shot3`
- `当前只解析了部分场景，禁止复用旧素材导出`

注意：前端禁用只是交互层保护，真正兜底必须在后端。

## 推荐修改文件

### 必改

- `app/services/storyboard_state.py`
- `app/routers/pipeline.py`
- `frontend/src/views/VideoGeneration.vue`

### 可能联动

- `tests/test_storyboard_state.py`
- `tests/test_pipeline_runtime.py`

## 建议测试用例

### 1. 新 storyboard 解析后清除旧资产

前置：

- 老 storyboard 有 `images/videos/transitions/timeline/final_video_url`

执行：

- 重新解析一个只包含部分场景的新 storyboard

预期：

- story meta 和 pipeline 中只保留新 storyboard 的 `storyboard`
- 旧 `videos/transitions/timeline/final_video_url` 被清空或裁剪掉

### 2. 缺主镜头视频时禁止导出

前置：

- 当前 storyboard 有 3 个 shots
- 只生成了 2 个主视频

预期：

- 前端按钮禁用
- 后端 `concat` 返回 400

### 3. 缺 transition 时禁止导出

前置：

- 当前 storyboard 有 3 个 shots
- 3 个主视频都存在
- 只生成了 1 个 transition

预期：

- 前端按钮禁用
- 后端 `concat` 返回 400

### 4. 旧 transition 不得混入新 storyboard

前置：

- 上一版 storyboard 有 `transition_a__b`
- 当前 storyboard 已变成 `shot-x -> shot-y`

预期：

- `transition_a__b` 不出现在当前 `timeline`
- 导出顺序只基于 `shot-x / shot-y`

### 5. 单镜头 storyboard 可直接导出

前置：

- 当前只有 1 个 shot
- 主视频已存在

预期：

- 不要求 transition
- 可以导出

## 建议验收标准

1. 重新解析 storyboard 后，旧素材不会再被当前导出流程读取。
2. “导出完整视频”只有在当前核心分镜和全部过渡分镜都生成完成时才可点击。
3. 后端即使收到错误的 `video_urls`，也不会导出不属于当前 storyboard 的素材。
4. 刷新页面、恢复历史状态后，导出判断仍与后端一致。

## 本次已完成

本次实际已先落地一个临时前端变更：

- `frontend/src/views/VideoGeneration.vue`
  - 已隐藏“生成语音”相关前端入口
  - 已停止页面初始化时加载语音列表

上面这份文档对应的是下一步“完整视频导出防串片”的改造说明，尚未在代码中完全实现。
