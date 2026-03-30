# API Key 管理指南

> 更新日期：2026-03-30

---

## 概述

AutoMedia 采用**三段式配置回退链**：

```
前端 Header / Body → .env 环境变量 → 内置默认值或 HTTP 400 错误
```

前端设置页面提供独立的文本、分镜专用文本、图片、视频配置块；服务商、API Key、Base URL、模型互不继承，`.env` 作为前端未填写时的服务端默认值。

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
| `scriptProvider` | `scriptProvider` | `""` |
| `scriptApiKey` | `scriptApiKey` | `""` |
| `scriptBaseUrl` | `scriptBaseUrl` | `""` |
| `scriptModel` | `scriptModel` | `""` |
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
| `useMock` | `VITE_ENABLE_MOCK=true` 且 `llmApiKey` 为空时启用 Mock 模式 |
| `effectiveLlmProvider/ApiKey/BaseUrl/Model` | 直接读对应 state |
| `effectiveImageApiKey/BaseUrl/Model` | 直接读对应 state |
| `effectiveVideoProvider/ApiKey/BaseUrl/Model` | 直接读对应 state |

### Mock 模式

`MOCK_ENABLED` 现在只在显式设置 `VITE_ENABLE_MOCK=true` 时启用。默认情况下，即使前端本地未填写 `llmApiKey`，前端也会保持真实模式，让后端继续使用 `.env` 中的默认 LLM 凭证。

Mock 模式下，`getHeaders()` 不发送任何 LLM 相关 Header，后端 `story_llm.py` 在 `api_key == ""` 时回退到 `story_mock.py`。

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
| `X-Script-Provider` | `effectiveScriptProvider` | 有值 |
| `X-Script-API-Key` | `effectiveScriptApiKey` | 有值 |
| `X-Script-Base-URL` | `effectiveScriptBaseUrl` | 有值 |
| `X-Script-Model` | `effectiveScriptModel` | 有值 |
| `X-Image-API-Key` | `effectiveImageApiKey` | 有值 |
| `X-Image-Base-URL` | `effectiveImageBaseUrl` | 有值 |
| `X-Video-Provider` | `effectiveVideoProvider` | 有值 |
| `X-Video-API-Key` | `effectiveVideoApiKey` | 有值 |
| `X-Video-Base-URL` | `effectiveVideoBaseUrl` | 有值 |

空值字段不发送 Header，由后端回退到 `.env`。

补充：
- 当前端本地没有显式配置 LLM，前端不会把默认展示值 `claude` 强行写进 `X-LLM-Provider`
- 这样后端可以正确使用 `.env` 中的 `DEFAULT_LLM_PROVIDER`
- 当前端本地没有填写 LLM Key 时，前端也不会发送 `X-LLM-Base-URL`
- 这样浏览器里保存的默认官方地址不会被后端误判成“自定义 Base URL”

---

## 后端三段式回退链（`app/core/api_keys.py`）

### LLM（`resolve_llm_config`）

```
X-LLM-API-Key header → .env <provider>_API_KEY → HTTP 400
X-LLM-Base-URL header → .env <provider>_BASE_URL
X-LLM-Provider header → settings.default_llm_provider（默认 claude）
X-LLM-Model header → 代码内 provider 默认模型
```

已支持的 Provider：`claude`、`openai`、`qwen`、`zhipu`、`gemini`、`siliconflow`

安全规则：
- 客户端提供 base_url 时，必须同时提供 api_key，禁止回退服务端凭证
- 未知/自定义 provider 必须同时提供 api_key 和 base_url

### Image（`image_config_dep`）

```
X-Image-API-Key header → .env SILICONFLOW_IMAGE_API_KEY / DOUBAO_IMAGE_API_KEY → HTTP 400
X-Image-Base-URL header → .env SILICONFLOW_IMAGE_BASE_URL / DOUBAO_IMAGE_BASE_URL
Request body model → .env DOUBAO_IMAGE_MODEL / SILICONFLOW_IMAGE_MODEL / DEFAULT_IMAGE_MODEL
```

后端使用 OpenAI 兼容的 `/images/generations` 接口，响应格式为 `{"images": [{"url": "..."}]}`。
前端不会发送 `X-Image-Provider`，因此后端会根据 `X-Image-Base-URL` 推断图片 provider。
若 `X-Image-Base-URL` 命中已知图片服务商（SiliconFlow / 豆包），即使前端没有传图片 Key，后端仍会继续回退到该图片服务商对应的 `.env` Key。
如果图片服务商是豆包 / 火山方舟，模型通常应填写端点 ID（`ep-...`）；前端未传时，后端会尝试读取 `.env` 中的 `DOUBAO_IMAGE_MODEL`。

### Video（`video_config_dep`）

```
X-Video-Provider header → "dashscope"（默认）
X-Video-API-Key header  → .env DASHSCOPE_VIDEO_API_KEY / KLING_VIDEO_API_KEY / MINIMAX_VIDEO_API_KEY / DOUBAO_VIDEO_API_KEY → HTTP 400
X-Video-Base-URL header → .env DASHSCOPE_VIDEO_BASE_URL / KLING_VIDEO_BASE_URL / MINIMAX_VIDEO_BASE_URL / DOUBAO_VIDEO_BASE_URL
Request body model → .env DASHSCOPE_VIDEO_MODEL / KLING_VIDEO_MODEL / MINIMAX_VIDEO_MODEL / DOUBAO_VIDEO_MODEL / DEFAULT_VIDEO_MODEL
```

已支持的 Provider：`dashscope`（Wan 系列）、`kling`（快手可灵）、`minimax`（海螺视频）、`doubao`（火山方舟）
前端若传入的是已知视频 provider 的默认 Base URL，即使未填写视频 Key，后端也会继续回退到对应视频 provider 的 `.env` Key。

---

## 视频提供商详情

### DashScope（默认）

- API 类型：DashScope 专有异步任务 API
- 提交：`POST {base_url}/services/aigc/image2video/video-synthesis`（`X-DashScope-Async: enable`）
- 轮询：`GET {base_url}/tasks/{task_id}`
- Auth：`Authorization: Bearer {api_key}`
- .env key：`DASHSCOPE_VIDEO_API_KEY`
- .env model：`DASHSCOPE_VIDEO_MODEL`

### Kling（快手可灵）

- API 类型：Kling REST API + JWT 鉴权
- 提交：`POST {base_url}/v1/videos/image2video`
- 轮询：`GET {base_url}/v1/videos/image2video/{task_id}`
- Auth：JWT token（由 access_key_id + secret_key 生成，有效期 30 分钟）
- **API Key 格式**：`access_key_id:secret_key`（冒号拼接两个字段，在可灵开放平台获取）
- .env key：`KLING_VIDEO_API_KEY`（同样用冒号格式）
- .env model：`KLING_VIDEO_MODEL`

### MiniMax 海螺视频

- API 类型：MiniMax 图生视频异步任务 API
- 提交：`POST {base_url}/v1/video_generation`
- 轮询：`GET {base_url}/v1/query/video_generation`
- 取回文件：`GET {base_url}/v1/files/retrieve`
- Auth：`Authorization: Bearer {api_key}`
- .env key：`MINIMAX_VIDEO_API_KEY`
- .env model：`MINIMAX_VIDEO_MODEL`

### 豆包 / 火山方舟 Ark

- 图片和视频模型都建议使用端点 ID（`ep-...`）
- 图片 .env key：`DOUBAO_IMAGE_API_KEY`
- 图片 .env base_url：`DOUBAO_IMAGE_BASE_URL`
- 图片模型：`DOUBAO_IMAGE_MODEL`
- 视频 .env key：`DOUBAO_VIDEO_API_KEY`
- 视频 .env base_url：`DOUBAO_VIDEO_BASE_URL`
- 视频模型：`DOUBAO_VIDEO_MODEL`

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
| `doubao` | 豆包（火山方舟） | `https://ark.cn-beijing.volces.com/api/v3` | OpenAI 兼容，模型一般填 `ep-...` |
| `custom` | 自定义 | 手动填写 | — |

### 视频提供商（`VIDEO_PROVIDERS`）

| Provider ID | 服务商 | Base URL | 后端支持 |
|-------------|--------|---------|---------|
| `dashscope` | 阿里云 DashScope | `https://dashscope.aliyuncs.com/api/v1` | ✅ |
| `kling` | 快手可灵 Kling | `https://api.klingai.com` | ✅ |
| `minimax` | MiniMax 海螺视频 | `https://api.minimaxi.chat` | ✅ |
| `doubao` | 豆包 Seedance（火山方舟） | `https://ark.cn-beijing.volces.com/api/v3` | ✅ |
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
│   │   ├── kling.py
│   │   ├── minimax.py
│   │   └── doubao.py
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
SILICONFLOW_API_KEY=sk-xxx

# 图片生成（SiliconFlow）
SILICONFLOW_IMAGE_API_KEY=sk-xxx
SILICONFLOW_IMAGE_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_IMAGE_MODEL=black-forest-labs/FLUX.1-schnell

# 图片生成（豆包 / 火山方舟）
DOUBAO_IMAGE_API_KEY=sk-xxx
DOUBAO_IMAGE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_IMAGE_MODEL=ep-xxxxxxxxxxxxxxxx

# 视频生成（DashScope）
DASHSCOPE_VIDEO_API_KEY=sk-xxx
DASHSCOPE_VIDEO_BASE_URL=https://dashscope.aliyuncs.com/api/v1
DASHSCOPE_VIDEO_MODEL=wan2.6-i2v-flash

# 视频生成（Kling）
KLING_VIDEO_API_KEY=access_key_id:secret_key         # Kling 格式
KLING_VIDEO_BASE_URL=https://api.klingai.com
KLING_VIDEO_MODEL=kling-v2-master

# 视频生成（MiniMax）
MINIMAX_VIDEO_API_KEY=sk-xxx
MINIMAX_VIDEO_BASE_URL=https://api.minimaxi.chat
MINIMAX_VIDEO_MODEL=video-01

# 视频生成（豆包 / 火山方舟，建议填写端点 ID）
DOUBAO_VIDEO_API_KEY=sk-xxx
DOUBAO_VIDEO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_VIDEO_MODEL=ep-yyyyyyyyyyyyyyyy
```

---

## Key 安全措施

- **日志脱敏**：`mask_key()` 只输出 `sk-a...xxxx` 格式
- **前置校验**：Key 缺失时在服务调用前返回 HTTP 400，不发起外部请求
- **SSRF 防护**：`validate_user_base_url()` 拒绝内网/loopback IP，可选开启 DNS 解析校验（`VALIDATE_BASE_URL_DNS=true`）
- **已知 Provider Base URL 规则**：客户端传入已知 provider 的默认 Base URL 时，允许继续回退到对应 `.env` Key
- **自定义 Base URL 规则**：客户端提供未知自定义 base_url 时必须同时提供 api_key，不回退服务端凭证

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
| HTTP 400：图片生成 API Key 未配置 | 前端未填图片 Key，且 `.env` 中对应图片服务商（如 `SILICONFLOW_IMAGE_API_KEY` / `DOUBAO_IMAGE_API_KEY`）也为空 | 填写 Key 或配置对应图片 `.env` |
| HTTP 400：视频生成 API Key 未配置 | 视频 Key 缺失 | 填写对应 provider Key |
| HTTP 400：使用自定义 Base URL 时必须同时提供 Key | 只填了未知自定义 base_url 未填 key | 两项都填 |
| HTTP 401：Api key is invalid | Key 正确格式但服务商拒绝 | 确认 Key 与 Base URL 属于同一服务商 |
| Kling 报错 "格式应为 access_key_id:secret_key" | Kling Key 未用冒号格式 | 检查 Key 格式 |
| 页面总是像 Mock | 是否误设了 `VITE_ENABLE_MOCK=true` | 关闭该环境变量并重启前端 |
