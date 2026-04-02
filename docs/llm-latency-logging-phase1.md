# LLM 耗时日志一期方案

## 目标

第一期只做后端埋点，不修改前端展示和接口响应结构。目标是让每一次 LLM 请求都能在服务端日志中看到：

- 是哪条业务触发的
- 走的是哪个 provider 和 model
- 总耗时是多少
- 流式请求的首 token 耗时是多少
- token 用量是多少
- 请求是否成功

## 实现范围

本次覆盖两条调用链：

1. 新的 provider 抽象链路
   - `app/services/llm/*.py`
   - `storyboard.py`
   - `story_context_service.py`
2. 旧的直连 OpenAI 兼容 SDK 链路
   - `app/services/story_llm.py`

这保证不会出现“只有 storyboard 有耗时日志，故事生成主链没有日志”的情况。

## 核心设计

### 1. 统一 telemetry 模块

新增 `app/services/llm/telemetry.py`，统一提供：

- `estimate_request_chars`
- `normalize_usage`
- `LLMCallTracker`

`LLMCallTracker` 负责：

- 请求开始时记录起始时间
- 流式返回时记录首个有效内容 chunk 的时间
- 请求完成时输出 `LLM_CALL`
- 超过阈值时额外输出 `LLM_SLOW`
- 异常时输出失败日志

补充约定：

- 正常成功请求的 `LLM_CALL` 使用 `INFO`
- 慢请求的 `LLM_CALL` 会提升到 `WARNING`
- 这样在只保留 `WARNING` 的日志环境里，`LLM_SLOW` 仍然能和对应的完整 `LLM_CALL` 配对查看

### 2. 统一日志字段

日志字段尽量保持扁平，方便 grep 和后续接入 ELK / Loki：

- `operation`
- `provider`
- `model`
- `latency_ms`
- `first_token_ms`
- `prompt_tokens`
- `completion_tokens`
- `request_chars`
- `response_chars`
- `success`
- `error_type`
- `story_id`
- `pipeline_id`
- `project_id`
- `episode`
- `mode`
- `change_type`

### 3. 只记元信息，不记敏感内容

一期日志不记录以下内容：

- prompt 原文
- 响应全文
- API Key
- 完整 base URL

只记录长度、上下文标识和模型信息，降低泄露风险。

## 当前接入点

### Provider 抽象链

- `OpenAIProvider`
- `ClaudeProvider`
- `QwenProvider`
- `GeminiProvider`
- `ZhipuProvider`

业务侧会把更有意义的 `operation` 透传下去，例如：

- `storyboard.parse`
- `story_context.extract_character_appearance`
- `story_context.extract_scene_style_cache`

### 旧 story_llm 直连链

以下方法已经加上埋点：

- `analyze_idea`
- `refine`
- `generate_outline`
- `chat`
- `generate_script`
- `world_building_start`
- `world_building_turn`
- `apply_chat`

其中流式接口会额外记录 `first_token_ms`。

## 配置项

新增两个后端配置项：

```env
LLM_TELEMETRY_ENABLED=true
LLM_SLOW_LOG_THRESHOLD_MS=5000
```

说明：

- `LLM_TELEMETRY_ENABLED`：总开关
- `LLM_SLOW_LOG_THRESHOLD_MS`：慢请求阈值，超过时打印 `LLM_SLOW`

## 日志示例

```text
LLM_CALL operation="storyboard.parse" provider="claude" model="claude-sonnet-4-6" latency_ms=3821 first_token_ms=614 prompt_tokens=1542 completion_tokens=711 request_chars=8450 response_chars=3921 success=true story_id="story-1" pipeline_id="pipe-1"
LLM_SLOW operation="storyboard.parse" provider="claude" model="claude-sonnet-4-6" latency_ms=3821 threshold_ms=3000 story_id="story-1" pipeline_id="pipe-1"
LLM_CALL operation="story.chat" provider="openai" model="gpt-4o-mini" latency_ms=912 success=false error_type="ReadTimeout" request_chars=1820 response_chars=0 story_id="story-2" mode="generic"
```

## 验证方式

建议先做三类验证：

1. 成功的非流式请求
   - 看 `latency_ms`、token、业务 `operation` 是否完整
2. 成功的流式请求
   - 看 `first_token_ms` 是否出现
3. 异常请求
   - 看 `success=false` 和 `error_type` 是否出现

## 二期建议

如果后续要前端展示耗时，不建议把耗时塞进现有 `usage` 结构。更稳妥的做法是单独扩展：

```json
{
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 60
  },
  "metrics": {
    "latency_ms": 3200,
    "first_token_ms": 580
  }
}
```

这样不会污染现有 token 统计逻辑，也更容易继续扩展成本、缓存命中率等指标。
