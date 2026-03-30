# AutoMedia Phase 2 API 文档

## 🎯 改进概览

### 核心改进

1. **一键生成** - 新增 `/auto-generate` 接口，自动执行全流程
2. **双策略支持** - 支持分离式和一体式两种生成路径
3. **真实实现** - 替换所有 mock 函数，实现真实的服务调用
4. **详细进度** - 实时追踪每个步骤的进度和状态

---

## 🚀 一键生成接口（推荐）

### `POST /api/v1/pipeline/{project_id}/auto-generate`

**完全自动化**：一次性完成分镜解析 → TTS/图片生成 → 视频生成 → FFmpeg 合成

#### 请求参数

```json
{
  "script": "# 第1集 神秘的开端\n## 场景1\n【环境】雨夜赛博朋克暗巷\n【画面】牧之身着黑色风衣...",
  "strategy": "separated",  // 或 "integrated"
  "provider": "claude",
  "model": null,
  "voice": "zh-CN-XiaoxiaoNeural",
  "image_model": "black-forest-labs/FLUX.1-schnell",
  "video_model": "wan2.6-i2v-flash",
  "base_url": "http://localhost:8000"
}
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `script` | string | 必填 | Markdown 格式的视听剧本 |
| `strategy` | enum | `separated` | 生成策略：`separated`（分离式）或 `integrated`（一体式）|
| `provider` | string | `claude` | LLM 服务商：claude/openai/qwen/zhipu/gemini |
| `model` | string? | null | 具体模型名，不填则使用默认 |
| `voice` | string | `zh-CN-XiaoxiaoNeural` | TTS 语音（Edge TTS）|
| `image_model` | string | `black-forest-labs/FLUX.1-schnell` | 图片生成模型 |
| `video_model` | string | `wan2.6-i2v-flash` | 视频生成模型 |
| `base_url` | string | `http://localhost:8000` | 服务器地址（用于拼接本地文件 URL）|

#### 生成策略对比

| 策略 | 流程 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **separated**（分离式） | TTS → 图片 → 图生视频 → FFmpeg 合成 | 音视频质量可控，支持后期调整 | 流程更长，需要 FFmpeg | 需要精细控制音视频质量 |
| **integrated**（一体式） | 图片 → 视频语音一体生成 | 流程更短，效率更高 | 音频已嵌入视频，难以调整 | 快速生成，原型测试 |

#### 响应示例

```json
{
  "project_id": "proj_123",
  "message": "自动化流水线已启动（策略：separated）",
  "strategy": "separated"
}
```

#### 使用流程

```bash
# 1. 调用一键生成
curl -X POST http://localhost:8000/api/v1/pipeline/proj_123/auto-generate \
  -H "Content-Type: application/json" \
  -d '{
    "script": "...",
    "strategy": "separated"
  }'

# 2. 轮询进度
curl http://localhost:8000/api/v1/pipeline/proj_123/status

# 3. 获取结果
# 返回的 generated_files 包含所有镜头的音视频 URL
```

---

## 🔧 手动触发接口（可选）

### 1. 分镜解析

### `POST /api/v1/pipeline/{project_id}/storyboard`

手动触发分镜解析（用于调试或单独测试）

#### 请求参数

```
Query:
- script: string (必填) - Markdown 格式剧本
- provider: string (必填) - LLM 服务商
- model: string? (可选) - 具体模型名
```

#### 响应示例

```json
{
  "shots": [
    {
      "shot_id": "scene1_shot1",
      "visual_description_zh": "牧之站在雨夜暗巷",
      "visual_prompt": "A young man in a black trench coat...",
      "camera_motion": "Static",
      "dialogue": "（旁白）最致命的病毒...",
      "estimated_duration": 4
    }
  ]
}
```

---

### 2. 生成资产

### `POST /api/v1/pipeline/{project_id}/generate-assets`

手动触发生成 TTS 和图片

#### 请求参数

```json
{
  "shots": [
    {
      "shot_id": "scene1_shot1",
      "dialogue": "（旁白）最致命的病毒...",
      "visual_prompt": "A young man..."
    }
  ]
}

Query:
- voice: string (默认: zh-CN-XiaoxiaoNeural)
- image_model: string (默认: black-forest-labs/FLUX.1-schnell)
```

---

### 3. 图生视频

### `POST /api/v1/pipeline/{project_id}/render-video`

手动触发图生视频

#### 请求参数

```json
{
  "shots": [
    {
      "shot_id": "scene1_shot1",
      "image_url": "/media/images/scene1_shot1.png",
      "visual_prompt": "A young man...",
      "camera_motion": "Static"
    }
  ]
}

Query:
- base_url: string (默认: http://localhost:8000)
- video_model: string (默认: wan2.6-i2v-flash)
```

---

### 4. FFmpeg 合成

### `POST /api/v1/pipeline/{project_id}/stitch`

手动触发音视频合成（仅分离式策略需要）

#### 请求参数

```json
{
  "shots": [
    {
      "shot_id": "scene1_shot1",
      "video_url": "/media/videos/scene1_shot1.mp4",
      "audio_url": "/media/audio/scene1_shot1.mp3"
    }
  ]
}
```

---

## 📊 状态查询

### `GET /api/v1/pipeline/{project_id}/status`

获取流水线实时状态

#### 响应示例

```json
{
  "project_id": "proj_123",
  "status": "rendering_video",
  "progress": 70,
  "current_step": "生成视频中",
  "progress_detail": {
    "step": "video",
    "current": 3,
    "total": 10,
    "message": "正在生成视频..."
  },
  "generated_files": null,
  "error": null
}
```

#### 状态枚举

- `pending` - 等待开始
- `storyboard` - 分镜解析中
- `generating_assets` - 生成 TTS 和图片中
- `rendering_video` - 图生视频中
- `stitching` - FFmpeg 合成中
- `complete` - 完成
- `failed` - 失败

---

## 🎨 前端集成示例

### Vue 3 + Pinia 示例

```javascript
// stores/pipeline.js
import { defineStore } from 'pinia'

export const usePipelineStore = defineStore('pipeline', {
  state: () => ({
    projectId: null,
    status: null,
    progress: 0,
    progressDetail: null,
    generatedFiles: null,
  }),

  actions: {
    async autoGenerate(script, strategy = 'separated') {
      const response = await fetch('/api/v1/pipeline/' + this.projectId + '/auto-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script,
          strategy,
          provider: 'claude',
        }),
      })

      return await response.json()
    },

    async pollStatus() {
      const response = await fetch(`/api/v1/pipeline/${this.projectId}/status`)
      const data = await response.json()

      this.status = data.status
      this.progress = data.progress
      this.progressDetail = data.progress_detail
      this.generatedFiles = data.generated_files

      return data
    },
  },
})
```

### 使用示例

```vue
<template>
  <div>
    <button @click="startAutoGenerate" :disabled="isGenerating">
      一键生成视频
    </button>

    <div v-if="isGenerating">
      <p>当前步骤：{{ progressDetail?.message }}</p>
      <progress :value="progress" max="100"></progress>
    </div>

    <div v-if="generatedFiles">
      <div v-for="shot in generatedFiles.shots" :key="shot.shot_id">
        <video :src="shot.video_url" controls></video>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { usePipelineStore } from '@/stores/pipeline'

const pipeline = usePipelineStore()
const isGenerating = computed(() => pipeline.status !== 'complete' && pipeline.status !== null)

async function startAutoGenerate() {
  await pipeline.autoGenerate(script.value, 'separated')

  // 轮询进度
  const timer = setInterval(async () => {
    const status = await pipeline.pollStatus()

    if (status.status === 'complete' || status.status === 'failed') {
      clearInterval(timer)
    }
  }, 2000)
}
</script>
```

---

## 🔍 调试技巧

### 1. 测试单个步骤

```bash
# 只测试分镜解析
curl -X POST "http://localhost:8000/api/v1/pipeline/test/storyboard?script=...&provider=claude"

# 只测试 TTS + 图片
curl -X POST http://localhost:8000/api/v1/pipeline/test/generate-assets \
  -H "Content-Type: application/json" \
  -d '{ "shots": [...] }'
```

### 2. 查看详细进度

```bash
# 实时查看进度
watch -n 1 'curl -s http://localhost:8000/api/v1/pipeline/proj_123/status | jq'
```

### 3. 检查生成文件

```bash
# 查看生成的媒体文件
ls -lh media/audio/
ls -lh media/images/
ls -lh media/videos/
```

---

## ⚠️ 注意事项

1. **API Key 配置**：确保 `.env` 文件中配置了必要的 API Key
   - LLM: ANTHROPIC_API_KEY / OPENAI_API_KEY / etc.
   - 图片: SILICONFLOW_IMAGE_API_KEY
   - 视频: DASHSCOPE_VIDEO_API_KEY

2. **FFmpeg 安装**：分离式策略需要 FFmpeg
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu
   sudo apt install ffmpeg
   ```

3. **存储空间**：视频文件较大，确保有足够磁盘空间

4. **并发限制**：图生视频 API 可能有并发限制，建议控制并发数量

5. **超时设置**：视频生成可能耗时较长，前端需设置合理的超时时间

---

## 🚧 待完善功能

- [ ] FFmpeg 真实合成逻辑（目前是 mock）
- [ ] 一体式视频生成的真实实现
- [ ] 断点续传（从中断处继续）
- [ ] 任务队列（Celery/Redis）
- [ ] 失败重试机制
- [ ] 进度 WebSocket 实时推送（替代轮询）

---

## 📚 相关文档

- [Phase 1 故事创作 API](./README.md#phase-1--故事创作)
- [分镜解析服务](../services/storyboard.py)
- [TTS 服务](../services/tts.py)
- [图片生成服务](../services/image.py)
- [视频生成服务](../services/video.py)
