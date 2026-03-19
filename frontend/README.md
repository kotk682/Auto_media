# Auto Media Frontend

基于 Vue 3 的剧本创作向导应用，引导用户完成从创意输入到剧本生成的完整流程。

---

## 快速开始

### 环境要求

- Node.js 16+
- npm

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

默认运行在 `http://localhost:5173`，需要后端服务同时运行在 `http://localhost:8000`。

### 构建生产版本

```bash
npm run build
```

---

## 整体架构

```
frontend/
├── src/
│   ├── main.js              # 应用入口，注册 Pinia、Router，启动时同步后端 config
│   ├── App.vue              # 根组件
│   ├── router/
│   │   └── index.js         # 路由定义（含 /settings）
│   ├── stores/
│   │   ├── story.js         # 故事流程全局状态
│   │   └── settings.js      # API 设置状态（含 useMock 同步）
│   ├── api/
│   │   └── story.js         # 后端 API 调用封装
│   ├── views/
│   │   ├── Step1Inspire.vue
│   │   ├── Step2Settings.vue
│   │   ├── Step3Script.vue
│   │   └── Step4Preview.vue
│   │   └── SettingsView.vue
│   ├── components/
│   │   ├── StepIndicator.vue
│   │   ├── StyleSelector.vue
│   │   ├── FollowUpOptions.vue
│   │   ├── OutlinePreview.vue
│   │   ├── CharacterGraph.vue
│   │   ├── SceneStream.vue
│   │   ├── ExportPanel.vue
│   │   └── ApiKeyModal.vue
│   └── style.css
├── vite.config.js           # Vite 配置（含 API 代理）
└── package.json
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | Vue 3 (Composition API + `<script setup>`) |
| 构建工具 | Vite 5 |
| 路由 | Vue Router 4 |
| 状态管理 | Pinia 2 |
| HTTP | Fetch API（含 SSE 流式处理） |

---

## 功能流程

```
Step 1 /step1   输入创意 + 选择风格
    ↓ POST /analyze-idea
Step 2 /step2   选择 AI 生成的故事设定
                可与 AI 实时对话完善设定（POST /chat SSE）
                AI 总结实时更新"你的灵感"区域
    ↓ POST /generate-outline
Step 3 /step3   左侧大纲 + 右侧人物关系图谱
                流式生成剧本（POST /generate-script SSE）
    ↓
Step 4 /step4   预览完整剧本 + 导出 JSON
                直接访问时自动重定向回 Step 1
```

### Step 1 — 灵感输入

- 文本框输入故事创意，支持随机灵感
- 风格选择：现代 / 古装 / 悬疑 / 甜宠
- 非 mock 模式下未设置 API Key 时弹窗提示

### Step 2 — 故事设定

- 展示 AI 返回的预设选项
- 自定义输入框支持与 AI 实时对话：
  - 清空按钮：清除输入框
  - 发送给 AI：流式返回总结，实时写入输入框
  - AI 回复完成后更新上方"你的灵感"区域
- 非 mock 模式下未设置 API Key 时弹窗提示

### Step 3 — 剧本生成

- 左侧：大纲预览
- 右侧：人物关系图谱（SVG，节点环形布局，带箭头和关系标签，sticky 固定）
- 点击生成后流式渲染场景（场景描述 + 角色对话）
- 非 mock 模式下未设置 API Key 时弹窗提示

### Step 4 — 预览导出

- 汇总展示：集数、角色数、场景数
- 完整剧本场景列表
- 导出为 JSON 文件
- 重新创作按钮（清空所有状态）

---

## 状态管理

### story store (`src/stores/story.js`)

```javascript
{
  currentStep: 1,
  storyId: null,
  input: { idea: '', style: '' },
  followUpOptions: [],
  selectedSetting: '',
  meta: null,               // { title, genre, episodes, theme }
  characters: [],           // [{ name, role, description }]
  relationships: [],        // [{ source, target, label }]
  outline: [],              // [{ episode, title, summary }]
  scenes: []                // [{ episode, title, scenes: [...] }]
}
```

### settings store (`src/stores/settings.js`)

```javascript
{
  backendUrl: '',           // 后端地址，留空走 Vite 代理
  provider: 'claude',       // LLM 服务商
  llmBaseUrl: '',           // LLM Base URL
  apiKey: '',               // API Key（仅存本地 localStorage）
  useMock: true,            // 从后端 /api/config 同步
}
```

---

## API 封装

`src/api/story.js` 封装四个接口：

```javascript
analyzeIdea(idea, style)
generateOutline(storyId, selectedSetting)
streamChat(storyId, message, onChunk, onDone, onError)  // SSE 逐字流
streamScript(storyId, onScene, onDone, onError)          // SSE 逐场景流
```

所有请求自动携带：
- `X-LLM-API-Key`：API Key
- `X-LLM-Base-URL`：LLM Base URL
- `X-LLM-Provider`：服务商标识

后端地址通过 `settings.backendUrl` 配置，留空走 Vite 代理 `/api → localhost:8000`。

---

## 组件说明

| 组件 | 用途 |
|------|------|
| `StepIndicator` | 顶部步骤进度条，右上角含"⚙ 设置"按钮 |
| `StyleSelector` | 风格选择按钮组（支持 v-model） |
| `FollowUpOptions` | 预设选项 + 自定义输入框 + AI 对话按钮 |
| `OutlinePreview` | 展示故事元数据、人物卡片、分集大纲 |
| `CharacterGraph` | SVG 人物关系图谱，节点环形布局，带箭头和关系标签 |
| `SceneStream` | 渲染场景描述和角色对话，支持流式加载动画 |
| `ExportPanel` | 将完整剧本数据导出为 JSON 文件 |
| `ApiKeyModal` | API Key 缺失或无效时的弹窗提示，引导前往设置 |

---

## 设置页 (`/settings`)

- 后端地址：FastAPI 服务地址，留空走代理
- 服务商下拉：选择后自动填入对应 LLM Base URL
- LLM Base URL：可手动修改
- API Key：本地存储，不上传服务器

支持的服务商：Anthropic Claude / OpenAI / 阿里云 Qwen / 智谱 GLM / Google Gemini / 自定义

---

## 样式规范

- 主色：`#6c63ff`（紫色）
- 辅助色：`#a78bfa`
- 中性色：`#e0e0e0`
- 错误色：`#e53935`
- 成功色：`#4caf50`
- 内容区最大宽度：`600px`（Step 3 为 `900px` 左右布局）
- 场景卡片带淡入动画，流式加载时显示弹跳指示器
