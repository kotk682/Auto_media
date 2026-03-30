# AutoMedia 快速测试指南

## 🚀 5 分钟快速测试自动化流水线

本指南帮助你快速测试新的自动化视频生成功能。

---

## 前置准备

### 1. 配置 API Keys

编辑 `.env` 文件，填入必要的 API Keys：

```bash
# LLM（用于分镜解析）
DEFAULT_LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...

# 图片生成
SILICONFLOW_IMAGE_API_KEY=sk-...

# 视频生成（阿里云通义万象）
DASHSCOPE_VIDEO_API_KEY=sk-...
```

### 2. 启动服务

```bash
python start.py
```

- 后端：http://localhost:8000
- 前端：http://localhost:5173

---

## 测试 1：一键生成（推荐）

### 使用 curl 测试

```bash
# 创建测试项目 ID
PROJECT_ID="test_$(date +%s)"

# 准备测试剧本（简化版）
SCRIPT="
# 第1集 神秘的开端

## 场景1
【环境】雨夜赛博朋克暗巷，霓虹灯闪烁
【画面】牧之身着黑色机能风衣，静立于阴影中，缓缓举起发光的科技毛笔
（旁白）最致命的病毒，往往是那些早已被人遗忘的字符。

## 场景2
【环境】虚拟数据空间，蓝色代码流环绕
【画面】特写牧之的眼睛，瞳孔中倒映着流动的代码
【牧之】系统已锁定，开始执行清除程序。
"

# 调用一键生成接口
curl -X POST "http://localhost:8000/api/v1/pipeline/${PROJECT_ID}/auto-generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"script\": \"${SCRIPT}\",
    \"strategy\": \"separated\",
    \"provider\": \"claude\",
    \"voice\": \"zh-CN-XiaoxiaoNeural\",
    \"image_model\": \"black-forest-labs/FLUX.1-schnell\",
    \"video_model\": \"wan2.6-i2v-flash\",
    \"base_url\": \"http://localhost:8000\"
  }"

echo "✅ 流水线已启动，项目 ID: ${PROJECT_ID}"
```

### 查看进度

```bash
# 实时查看进度（每 2 秒刷新）
watch -n 2 "curl -s http://localhost:8000/api/v1/pipeline/${PROJECT_ID}/status | jq"
```

### 查看生成的文件

```bash
# 查看音频
ls -lh media/audio/*.mp3

# 查看图片
ls -lh media/images/*.png

# 查看视频
ls -lh media/videos/*.mp4
```

---

## 测试 2：手动分步测试（调试用）

### Step 1: 分镜解析

```bash
PROJECT_ID="manual_test_$(date +%s)"

curl -X POST "http://localhost:8000/api/v1/pipeline/${PROJECT_ID}/storyboard" \
  -H "Content-Type: application/json" \
  -G \
  --data-urlencode "script=# 第1集 测试
## 场景1
【环境】夜晚城市街道
【画面】一个穿风衣的人站在路灯下
【角色A】这是一个测试。" \
  --data-urlencode "provider=claude"

# 保存返回的 shots 数据，下一步需要
```

### Step 2: 生成 TTS + 图片

```bash
# 使用上一步返回的 shots 数据
curl -X POST "http://localhost:8000/api/v1/pipeline/${PROJECT_ID}/generate-assets" \
  -H "Content-Type: application/json" \
  -d '{
    "shots": [
      {
        "shot_id": "scene1_shot1",
        "dialogue": "这是一个测试。",
        "visual_prompt": "A person in a trench coat standing under a streetlight at night, cinematic lighting, 8k resolution, highly detailed, photorealistic, --ar 16:9"
      }
    ]
  }'
```

### Step 3: 图生视频

```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/${PROJECT_ID}/render-video" \
  -H "Content-Type: application/json" \
  -d '{
    "shots": [
      {
        "shot_id": "scene1_shot1",
        "image_url": "/media/images/scene1_shot1.png",
        "visual_prompt": "A person in a trench coat standing under a streetlight at night",
        "camera_motion": "Static"
      }
    ]
  }'
```

---

## 测试 3：测试不同策略

### 分离式策略（separated）

```bash
# TTS → 图片 → 视频 → FFmpeg 合成
curl -X POST .../auto-generate \
  -d '{"script": "...", "strategy": "separated"}'
```

**优点**：音视频质量可控，支持后期调整
**缺点**：流程更长，需要 FFmpeg
**适用**：需要精细控制的项目

### 一体式策略（integrated）

```bash
# 图片 → 视频语音一体生成
curl -X POST .../auto-generate \
  -d '{"script": "...", "strategy": "integrated"}'
```

**优点**：流程更短，效率更高
**缺点**：音频已嵌入视频，难以调整
**适用**：快速原型，测试

---

## 测试 4：Python 脚本测试

创建 `test_pipeline.py`：

```python
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000"
PROJECT_ID = f"test_{int(time.time())}"

async def test_auto_generate():
    script = """
# 第1集 测试视频

## 场景1
【环境】夜晚城市街道
【画面】一个穿黑色风衣的人站在路灯下，雨滴飘落
（旁白）这是一个自动化测试视频。
"""

    # 启动自动生成
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/pipeline/{PROJECT_ID}/auto-generate",
            json={
                "script": script,
                "strategy": "separated",
                "provider": "claude",
            },
        )
        print("✅ 流水线已启动:", response.json())

    # 轮询进度
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            response = await client.get(
                f"{BASE_URL}/api/v1/pipeline/{PROJECT_ID}/status"
            )
            data = response.json()
            print(f"⏳ 进度: {data['progress']}% - {data['current_step']}")

            if data["status"] in ["complete", "failed"]:
                print("✅ 完成!" if data["status"] == "complete" else "❌ 失败")
                print("生成文件:", json.dumps(data.get("generated_files"), indent=2, ensure_ascii=False))
                break

            await asyncio.sleep(3)

if __name__ == "__main__":
    import time
    asyncio.run(test_auto_generate())
```

运行：

```bash
python test_pipeline.py
```

---

## 常见问题排查

### 1. API Key 错误

```bash
# 检查环境变量
cat .env | grep API_KEY

# 测试 API 连通性
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

### 2. 图片/视频生成失败

- 检查 SILICONFLOW_IMAGE_API_KEY 和 DASHSCOPE_VIDEO_API_KEY
- 检查账户余额
- 查看后端日志：`python start.py` 输出

### 3. 进度卡住不动

```bash
# 检查后端日志
# 查看是否有错误信息

# 检查后台任务
ps aux | grep uvicorn

# 重启服务
python start.py
```

### 4. 磁盘空间不足

```bash
# 查看磁盘空间
df -h

# 清理旧文件
rm -rf media/audio/*
rm -rf media/images/*
rm -rf media/videos/*
```

---

## 性能基准

基于 2 个场景的测试：

| 步骤 | 耗时 | 备注 |
|------|------|------|
| 分镜解析 | ~5s | 取决于 LLM 速度 |
| TTS 生成 | ~10s | Edge TTS，并发处理 |
| 图片生成 | ~30s | FLUX.1-schnell，并发处理 |
| 视频生成 | ~3-5min | 通义万象，异步队列 |
| **总计** | **~4-6min** | 2 个场景 |

---

## 下一步

- [ ] 集成到前端（Step4 预览页添加"一键生成"按钮）
- [ ] 测试不同风格的故事
- [ ] 调整生成参数（语音、图片、视频模型）
- [ ] 实现 FFmpeg 真实合成

---

## 反馈与改进

如有问题或建议，请查看：
- [PIPELINE_API.md](./PIPELINE_API.md) - 完整 API 文档
- [README.md](./README.md) - 项目概览
