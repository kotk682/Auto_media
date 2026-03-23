# API Key 管理指南

> 更新日期：2026-03-23

---

## 概述

AutoMedia 采用**三段式 Key 回退链**：

```
前端 Header → .env 环境变量 → HTTP 400 错误
```

前端设置页面提供三个独立配置块（文本 / 图片 / 视频），各模块均有独立的服务商、API Key、Base URL 和模型选择，互不继承。

---

## 前端配置体系（`stores/settings.js`）

### State 字段

| 字段 | localStorage key | 默认值 |
|------|-----------------|--------|
| `backendUrl` | `backendUrl` | `""` |
| `llmProvider` | `llmProvider` | `claude` |
| `llmApiKey` | `llmApiKey` | `""` |
| `llmBaseUrl` | `llmBaseUrl` | `""` |
| `llmModel` | `llmModel` | `""` |
| `imageProvider` | `imageProvider` | `siliconflow` |
| `imageApiKey` | `imageApiKey` | `""` |
| `imageBaseUrl` | `imageBaseUrl` | `""` |
| `imageModel` | `imageModel` | `""` |
| `videoProvider` | `videoProvider` | `dashscope` |
| `videoApiKey` | `videoApiKey` | `""` |
| `videoBaseUrl` | `videoBaseUrl` | `""` |
| `videoModel` | `videoModel` | `""` |

### Getters

| Getter | 说明 |
|--------|------|
| `useMock` | `MOCK_ENABLED && !llmApiKey`，LLM Key 未填时启用 Mock 模式 |
| `effectiveLlmProvider/ApiKey/BaseUrl/Model` | 直接读对应 state |
| `effectiveImageApiKey/BaseUrl/Model` | 直接读对应 state |
| `effectiveVideoProvider/ApiKey/BaseUrl/Model` | 直接读对应 state |

### Mock 模式

`MOCK_ENABLED = true`（`settings.js` 顶部常量）。Mock 模式下，`getHeaders()` 不发送任何 LLM 相关 Header，后端 `story_llm.py` 在 `api_key == ""` 时回退到 `story_mock.py`。发布时将常量改为 `false` 即可禁用。

### localStorage 迁移（migrateV1）

初始化时自动执行一次：将旧版 `apiKey` → `llmApiKey`，`provider` → `llmProvider`，并清除旧字段（`textEnabled`、`imageEnabled`、`videoEnabled` 等）。

---

## 请求头规范（`api/story.js getHeaders()`）

| HTTP Header | Getter | 发送条件 |
|-------------|--------|---------|
| `X-LLM-API-Key` | `effectiveLlmApiKey` | 非 Mock 模式且有值 |
| `X-LLM-Base-URL` | `effectiveLlmBaseUrl` | 非 Mock 模式且有值 |
| `X-LLM-Provider` | `effectiveLlmProvider` | 非 Mock 模式且有值 |
| `X-LLM-Model` | `effectiveLlmModel` | 非 Mock 模式且有值 |
| `X-Image-API-Key` | `effectiveImageApiKey` | 有值 |
| `X-Image-Base-URL` | `effectiveImageBaseUrl` | 有值 |
| `X-Video-Provider` | `effectiveVideoProvider` | 有值 |
| `X-Video-API-Key` | `effectiveVideoApiKey` | 有值 |
| `X-Video-Base-URL` | `effectiveVideoBaseUrl` | 有值 |

空值字段不发送 Header，由后端回退到 `.env`。

---

## 后端三段式回退链（`app/core/api_keys.py`）

### LLM（`resolve_llm_config`）

```
X-LLM-API-Key header → .env <provider>_API_KEY → HTTP 400
X-LLM-Base-URL header → .env <provider>_BASE_URL
X-LLM-Provider header → settings.default_llm_provider（默认 claude）
```

已支持的 Provider：`claude`、`openai`、`qwen`、`zhipu`、`gemini`、`siliconflow`

安全规则：
- 客户端提供 base_url 时，必须同时提供 api_key，禁止回退服务端凭证
- 未知/自定义 provider 必须同时提供 api_key 和 base_url

### Image（`image_config_dep`）

```
X-Image-API-Key header → .env SILICONFLOW_API_KEY → HTTP 400
X-Image-Base-URL header → .env SILICONFLOW_BASE_URL
```

后端使用 OpenAI 兼容的 `/images/generations` 接口，响应格式为 `{"images": [{"url": "..."}]}`。

### Video（`video_config_dep`）

```
X-Video-Provider header → "dashscope"（默认）
X-Video-API-Key header  → .env DASHSCOPE_API_KEY / KLING_API_KEY → HTTP 400
X-Video-Base-URL header → .env DASHSCOPE_BASE_URL / KLING_BASE_URL
```

已支持的 Provider：`dashscope`（Wan 系列）、`kling`（快手可灵）

---

## 视频提供商详情

### DashScope（默认）

- API 类型：DashScope 专有异步任务 API
- 提交：`POST {base_url}/services/aigc/image2video/video-synthesis`（`X-DashScope-Async: enable`）
- 轮询：`GET {base_url}/tasks/{task_id}`
- Auth：`Authorization: Bearer {api_key}`
- .env key：`DASHSCOPE_API_KEY`

### Kling（快手可灵）

- API 类型：Kling REST API + JWT 鉴权
- 提交：`POST {base_url}/v1/videos/image2video`
- 轮询：`GET {base_url}/v1/videos/image2video/{task_id}`
- Auth：JWT token（由 access_key_id + secret_key 生成，有效期 30 分钟）
- **API Key 格式**：`access_key_id:secret_key`（冒号拼接两个字段，在可灵开放平台获取）
- .env key：`KLING_API_KEY`（同样用冒号格式）

---

## 服务商与模型列表

### LLM 提供商（`LLM_PROVIDERS`）

| Provider ID | 服务商 | Base URL |
|-------------|--------|---------|
| `claude` | Anthropic Claude | `https://api.anthropic.com` |
| `openai` | OpenAI | `https://api.openai.com/v1` |
| `siliconflow` | SiliconFlow | `https://api.siliconflow.cn/v1` |
| `qwen` | 阿里云 Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `zhipu` | 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4/` |
| `gemini` | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `custom` | 自定义 | 手动填写 |

### 图片提供商（`IMAGE_PROVIDERS`）

| Provider ID | 服务商 | Base URL | 接口格式 |
|-------------|--------|---------|---------|
| `siliconflow` | SiliconFlow | `https://api.siliconflow.cn/v1` | OpenAI 兼容（SiliconFlow 格式） |
| `openai` | OpenAI | `https://api.openai.com/v1` | OpenAI DALL-E |
| `zhipu` | 智谱 CogView | `https://open.bigmodel.cn/api/paas/v4/` | OpenAI 兼容 |
| `custom` | 自定义 | 手动填写 | — |

### 视频提供商（`VIDEO_PROVIDERS`）

| Provider ID | 服务商 | Base URL | 后端支持 |
|-------------|--------|---------|---------|
| `dashscope` | 阿里云 DashScope | `https://dashscope.aliyuncs.com/api/v1` | ✅ |
| `kling` | 快手可灵 Kling | `https://api.klingai.com` | ✅ |
| `custom` | 自定义 | 手动填写 | — |

---

## 后端项目结构

```
app/
├── core/
│   ├── api_keys.py        # Key 提取、resolve、SSRF 防护、Depends 函数
│   └── config.py          # .env 配置映射（pydantic Settings）
├── services/
│   ├── llm/               # LLM 多提供商工厂（claude/openai/qwen/zhipu/gemini）
│   │   ├── base.py
│   │   ├── factory.py
│   │   └── ...
│   ├── video_providers/   # 视频多提供商工厂
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── dashscope.py
│   │   └── kling.py
│   ├── image.py           # 图片生成（OpenAI 兼容接口）
│   ├── video.py           # 视频生成入口（调用 video_providers 工厂）
│   └── story_llm.py       # LLM 调用（含 Mock 回退）
└── routers/
    ├── pipeline.py        # 流水线路由
    └── video.py           # 视频路由
```

---

## .env 配置参考

```bash
# LLM providers
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
QWEN_API_KEY=sk-xxx
ZHIPU_API_KEY=xxx
GEMINI_API_KEY=xxx
SILICONFLOW_API_KEY=sk-xxx       # LLM + 图片共用

# 图片生成（SiliconFlow）
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1   # 可选，有默认值

# 视频生成
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1  # 可选

KLING_API_KEY=access_key_id:secret_key               # Kling 格式
KLING_BASE_URL=https://api.klingai.com               # 可选
```

---

## Key 安全措施

- **日志脱敏**：`mask_key()` 只输出 `sk-a...xxxx` 格式
- **前置校验**：Key 缺失时在服务调用前返回 HTTP 400，不发起外部请求
- **SSRF 防护**：`validate_user_base_url()` 拒绝内网/loopback IP，可选开启 DNS 解析校验（`VALIDATE_BASE_URL_DNS=true`）
- **自定义 Base URL 规则**：客户端提供 base_url 时必须同时提供 api_key，不回退服务端凭证

---

## 典型配置场景

### 场景 1：文本用 Claude，图片用 SiliconFlow，视频用 DashScope

- 文本：服务商 Claude，填写 Anthropic Key
- 图片：服务商 SiliconFlow，填写 SiliconFlow Key
- 视频：服务商 DashScope，填写 DashScope Key

### 场景 2：视频用 Kling

- 视频：服务商 Kling，API Key 填写 `access_key_id:secret_key`（冒号拼接）

### 场景 3：全部使用 .env（生产环境）

前端设置页不填写任何 Key，在 `.env` 中配置所有服务的 Key，前端 Header 为空，后端自动回退。

---

## 故障排查

| 错误 | 原因 | 解决 |
|------|------|------|
| HTTP 400：图片生成 API Key 未配置 | 前端未填图片 Key 且 `.env` 无 `SILICONFLOW_API_KEY` | 填写 Key 或配置 `.env` |
| HTTP 400：视频生成 API Key 未配置 | 视频 Key 缺失 | 填写对应 provider Key |
| HTTP 400：自定义服务商必须同时提供 Key 和 Base URL | 只填了 base_url 未填 key | 两项都填 |
| HTTP 401：Api key is invalid | Key 正确格式但服务商拒绝 | 确认 Key 与 Base URL 属于同一服务商 |
| Kling 报错 "格式应为 access_key_id:secret_key" | Kling Key 未用冒号格式 | 检查 Key 格式 |
| Mock 模式 400 | 发送了 LLM Provider Header 但 Key 为空 | 检查 `useMock` 是否正确屏蔽 LLM Headers |
