# Auto Media Backend

基于 FastAPI 的故事生成 API 服务，支持 mock 模式和真实 LLM 调用。

---

## 快速开始

### 环境要求

- Python 3.9+
- pip3

### 安装依赖

```bash
pip3 install -r requirements.txt
```

### 配置环境变量

编辑 `.env` 文件：

```env
USE_MOCK=true   # true 使用 mock 数据，false 接入真实 LLM
```

### 启动服务

```bash
uvicorn app.main:app --reload
# 或
python3 -m uvicorn app.main:app --reload
```

服务默认运行在 `http://localhost:8000`

- Swagger 文档：`http://localhost:8000/docs`
- ReDoc 文档：`http://localhost:8000/redoc`

---

## 整体架构

```
backend/
├── app/
│   ├── main.py              # FastAPI 应用入口，CORS 配置，/api/config 端点
│   ├── api/
│   │   └── story.py         # 路由层：定义 API 端点
│   ├── models/
│   │   └── story.py         # 数据模型：Pydantic 请求/响应结构
│   └── services/
│       ├── llm_service.py   # 服务层：mock/真实 LLM 切换入口
│       └── mock_service.py  # Mock 实现：内存存储 + 预设数据
├── .env                     # 环境变量
└── requirements.txt         # 依赖列表（fastapi, uvicorn, python-dotenv, openai）
```

### 分层设计

```
请求 → 路由层 (api/) → 服务层 (services/) → 数据模型 (models/)
```

- **路由层**：接收请求、读取 LLM 相关 header、调用服务、返回响应
- **服务层**：业务逻辑，`chat` 函数根据是否有 API Key 自动切换 mock/真实 LLM
- **数据模型**：Pydantic 模型，负责请求/响应的类型校验和序列化

---

## API 接口

### GET `/api/config`

返回当前后端配置，前端启动时调用以同步 mock 模式状态。

**响应：**
```json
{ "use_mock": true }
```

---

所有故事接口前缀：`/api/v1/story`

### POST `/analyze-idea`

分析故事创意，返回风格化的后续选项。

**请求体：**
```json
{
  "idea": "一个穿越到古代的现代女孩",
  "style": "古装"
}
```

**响应：**
```json
{
  "story_id": "uuid-string",
  "follow_up_options": [
    { "id": "opt1", "label": "权谋争斗", "value": "以宫廷权谋为主线" }
  ]
}
```

---

### POST `/generate-outline`

根据选定的故事设定生成大纲，包含人物、人物关系和分集概要。

**请求体：**
```json
{
  "story_id": "uuid-string",
  "selected_setting": "宫廷权谋"
}
```

**响应：**
```json
{
  "story_id": "uuid-string",
  "meta": { "title": "故事标题", "genre": "古装", "episodes": 6, "theme": "主题" },
  "characters": [{ "name": "角色名", "role": "主角", "description": "描述" }],
  "relationships": [{ "source": "角色A", "target": "角色B", "label": "关系" }],
  "outline": [{ "episode": 1, "title": "标题", "summary": "概要" }]
}
```

---

### POST `/chat`

与 AI 实时对话，流式返回总结建议。支持 LLM header 配置。

**请求 header（可选）：**
```
X-LLM-API-Key: sk-...
X-LLM-Base-URL: https://dashscope.aliyuncs.com/compatible-mode/v1
X-LLM-Provider: qwen
```

**请求体：**
```json
{ "story_id": "uuid-string", "message": "用户输入" }
```

**响应（SSE 流）：**
```
data: 根

data: 据

data: 你

data: [DONE]
```

- 有 API Key → 调用真实 LLM（OpenAI 兼容格式）
- 无 API Key → 返回 mock 回复
- 出错时返回 `data: [ERROR] 错误信息`

---

### POST `/generate-script`

流式生成剧本场景。

**请求体：**
```json
{ "story_id": "uuid-string" }
```

**响应（SSE 流）：**
```
data: {"episode": 1, "title": "场景标题", "scenes": [...]}

data: [DONE]
```

每个 `scenes` 元素：
```json
{
  "scene_number": 1,
  "location": "场景地点",
  "description": "场景描述",
  "dialogues": [{ "character": "角色名", "line": "台词" }]
}
```

---

## 数据流

```
Step 1: POST /analyze-idea
        → 生成 story_id，存入内存
        → 返回风格化选项

Step 2: POST /generate-outline
        → 返回元数据、人物、人物关系、分集概要

       POST /chat（可选，多次）
        → 用户与 AI 对话完善设定

Step 3: POST /generate-script
        → 流式返回每集场景的描述和台词
        → 以 [DONE] 标记结束
```

---

## 扩展：接入真实 LLM

`chat` 接口已支持真实 LLM，通过请求 header 传入配置即可。

其他接口（analyze、outline、script）接入真实 LLM 需在 `app/services/llm_service.py` 中实现对应函数（当前为 `NotImplementedError`）。

支持的 provider 及默认模型：

| Provider | 模型 |
|----------|------|
| qwen | qwen-plus |
| openai | gpt-4o-mini |
| zhipu | glm-4-flash |
| gemini | gemini-2.0-flash |
| claude | claude-sonnet-4-6 |

---

## 注意事项

- 当前使用内存存储，服务重启后数据清空
- 无鉴权机制，所有接口公开访问
- CORS 仅允许 `http://localhost:5173`（前端开发服务器）
- API Key 由前端通过 header 传入，后端不存储
