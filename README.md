# AutoMedia Backend

AI 驱动的短视频自动生成平台后端。输入一个种子想法，经过访谈问答、脚本生成、分镜解析、TTS、图片生成、图生视频、FFmpeg 合成，输出一条完整短视频。

---

## 项目结构

```
automedia/
├── .env.example              # 环境变量模板
├── requirements.txt
└── app/
    ├── main.py               # FastAPI 入口
    ├── core/
    │   ├── config.py         # 全局配置（读取 .env）
    │   └── database.py       # SQLAlchemy async 引擎
    ├── models/
    │   └── project.py        # ORM 模型
    ├── schemas/
    │   ├── interview.py      # 访谈状态机 Pydantic 模型
    │   ├── storyboard.py     # 分镜 Pydantic 模型
    │   └── pipeline.py       # 流水线状态 Pydantic 模型
    ├── routers/
    │   ├── projects.py       # Phase 1 API（访谈 + 脚本）
    │   └── pipeline.py       # Phase 2 API（分镜 + 资产 + 视频）
    └── services/
        ├── storyboard.py     # 分镜解析服务（LLM Prompt）
        └── llm/
            ├── base.py       # 抽象接口
            ├── factory.py    # Provider 工厂
            ├── claude.py     # Anthropic Claude
            ├── openai.py     # OpenAI / 兼容接口
            ├── qwen.py       # 阿里云 Qwen
            ├── zhipu.py      # 智谱 GLM
            └── gemini.py     # Google Gemini
```

---

## 快速开始

### 1. 环境要求

- Python 3.12+
- （可选）FFmpeg — 模块 E 合成视频时需要

### 2. 安装依赖

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key 和（可选）中转站地址：

```env
DEFAULT_LLM_PROVIDER=claude

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com   # 中转站改这里

OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1

QWEN_API_KEY=...
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

ZHIPU_API_KEY=...
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

GEMINI_API_KEY=...
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload
```

访问 `http://localhost:8000/docs` 查看交互式 API 文档。

---

## API 概览

### Phase 1 — 访谈与脚本（同事负责实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/init` | 创建项目，传入种子想法 |
| POST | `/api/v1/projects/{id}/chat` | 提交访谈答案，推进状态机 |
| GET  | `/api/v1/projects/{id}/script` | 获取生成的脚本 |

### Phase 2 — 流水线

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/pipeline/{id}/storyboard` | 脚本 → 分镜 JSON（调用 LLM） |
| POST | `/api/v1/pipeline/{id}/generate-assets` | 触发 TTS + 图片生成 |
| POST | `/api/v1/pipeline/{id}/render-video` | 触发图生视频（异步队列） |
| GET  | `/api/v1/pipeline/{id}/status` | 轮询渲染进度 |
| POST | `/api/v1/pipeline/{id}/stitch` | FFmpeg 合成最终视频 |

#### 分镜接口示例

```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/proj_001/storyboard" \
  -G --data-urlencode "script=这是一段视频脚本内容..." \
  --data-urlencode "provider=claude"
```

调用时可通过 `provider` 参数临时切换 LLM，不填则使用 `.env` 中的 `DEFAULT_LLM_PROVIDER`。

---

## 模块进度

| 模块 | 说明 | 状态 |
|------|------|------|
| 模块 A | 分镜引擎（LLM 解析脚本） | ✅ 完成 |
| 模块 B | TTS 语音生成 | 🔲 待开发 |
| 模块 C | 关键帧图片生成 | 🔲 待开发 |
| 模块 D | 图生视频异步队列 | 🔲 待开发 |
| 模块 E | FFmpeg 合成 | 🔲 待开发 |

---

## LLM Provider 切换

所有 provider 实现统一的 `BaseLLMProvider` 接口，切换只需改 `.env`：

```env
DEFAULT_LLM_PROVIDER=qwen  # claude / openai / qwen / zhipu / gemini
```

支持中转站：每个 provider 都有独立的 `*_BASE_URL` 配置项，直接替换为你的中转地址即可。
