# 首尾帧功能测试指南（网页版）

> **更新日期**：2026-03-25
> **状态**：✅ 后端已完全支持，可以在网页上测试

---

## ✅ 已完成的更新

### 1. 后端代码（100%完成）

- ✅ `app/services/video_providers/doubao.py` - 支持首尾帧
- ✅ `app/services/video.py` - `generate_video()` 和 `generate_videos_batch()` 都支持
- ✅ API接口自动兼容 - 前端可以在 shot 数据中添加 `last_frame_url` 字段

---

## 🚀 如何在网页上测试

### 方法1：手动修改分镜数据（最简单）⭐ 推荐

**步骤**：

1. **启动系统**
   ```bash
   python start.py
   ```

2. **在网页上生成分镜**
   - 输入剧本
   - 点击"生成分镜"
   - 等待分镜生成完成

3. **手动准备尾帧图片**
   - 从生成的图片中选一张作为尾帧
   - 或者自己生成一张尾帧图片
   - 放到 `media/images/` 目录

4. **修改分镜数据（前端）**
   - 在前端代码中，找到 `render-video` 调用
   - 在 `shots_data` 中添加 `last_frame_url` 字段

   **示例**：
   ```javascript
   // 原始数据
   const shotsData = [
     {
       shot_id: "scene1_shot1",
       image_url: "/media/images/scene1_shot1.png",
       visual_prompt: "...",
       camera_motion: "..."
     }
   ];

   // 修改后（添加尾帧）
   const shotsData = [
     {
       shot_id: "scene1_shot1",
       image_url: "/media/images/scene1_shot1.png",  // 首帧
       last_frame_url: "/media/images/scene1_shot1_end.png",  // ← 添加尾帧
       visual_prompt: "从站立姿势自然过渡到坐在椅子上",  // ← 修改Prompt
       camera_motion: "..."
     }
   ];
   ```

5. **生成视频**
   - 点击"生成视频"
   - 观察效果

---

### 方法2：通过API直接测试（开发者）

**使用 curl 或 Postman**：

```bash
# 准备测试数据
curl -X POST http://localhost:8000/api/v1/video/{project_id}/generate \
  -H "Content-Type: application/json" \
  -H "X-Video-API-Key: your-doubao-api-key" \
  -H "X-Video-Base-URL: https://ark.cn-beijing.volces.com/api/v3" \
  -H "X-Video-Provider: doubao" \
  -d '{
    "shots": [
      {
        "shot_id": "test_transition",
        "image_url": "/media/images/test_firstframe.png",
        "last_frame_url": "/media/images/test_lastframe.png",
        "final_video_prompt": "从站立姿势自然过渡到坐在椅子上，动作流畅"
      }
    ],
    "model": "doubao-seedance-1-5-pro-251215"
  }'
```

---

## 🎯 测试场景建议

### 场景1：简单动作过渡

**首帧**：人物站在门口
**尾帧**：人物坐在椅子上
**Prompt**：从站立姿势自然过渡到坐在椅子上

**预期效果**：
- ✅ 人物准确从站立状态过渡到坐姿
- ✅ 动作流畅自然
- ✅ 结束姿势与尾帧一致

---

### 场景2：场景切换

**首帧**：办公室场景（场景1最后一帧）
**尾帧**：会议室场景（场景2第一帧）
**Prompt**：平滑的场景切换

**预期效果**：
- ✅ 场景平滑过渡
- ✅ 无跳切感
- ✅ 视觉连贯

---

### 场景3：连续动作

**首帧**：手伸向门把手
**尾帧**：手握住门把手
**Prompt**：连续的伸手抓握动作

**预期效果**：
- ✅ 动作连续流畅
- ✅ 手部姿势准确
- ✅ 无抖动或跳跃

---

## 📊 对比测试

### 测试1：单帧 vs 双帧

**步骤**：
1. 先用单帧I2V生成一个视频（不提供 `last_frame_url`）
2. 再用双帧过渡生成同样场景的视频（提供 `last_frame_url`）
3. 对比两者质量

**对比指标**：
- 动作准确性：是否准确达到目标状态？
- 场景一致性：场景元素是否保持一致？
- 整体质量：哪个更自然流畅？

---

## ⚙️ 技术细节

### 前端需要做的修改（可选）

如果你想在前端自动支持尾帧，可以修改：

**文件**：`frontend/src/components/VideoGenerator.vue`（示例）

```javascript
// 在构建 shots_data 时添加尾帧支持
const shotsData = shots.map((shot, index) => {
  const data = {
    shot_id: shot.shot_id,
    image_url: shot.image_url,
    final_video_prompt: shot.final_video_prompt,
    camera_motion: shot.camera_setup.movement,
  };

  // 如果需要尾帧，添加 last_frame_url
  // 例如：为场景切换镜头自动添加尾帧
  if (shouldUseLastFrame(shot, shots[index + 1])) {
    data.last_frame_url = shots[index + 1]?.image_url || "";
  }

  return data;
});
```

---

## 🎨 首帧和尾帧图片的生成

### 选项1：手动准备图片

1. 使用现有的图片生成工具
2. 生成首帧和尾帧两张图片
3. 确保两张图片中的人物/场景一致
4. 上传到 `media/images/` 目录

---

### 选项2：自动生成（需要更多开发）

**未来可以实现**：

1. 在分镜生成阶段，为每个镜头生成：
   - 首帧图片（`image_url`）
   - 尾帧图片（`last_frame_url`）

2. 修改 `parse_script_to_storyboard()` 函数：
   ```python
   # 生成首帧
   first_frame = await generate_image(...)

   # 生成尾帧（基于首帧+动作描述）
   last_frame = await generate_last_frame(first_frame, action_description)

   # 保存到shot对象
   shot.image_url = first_frame["image_url"]
   shot.last_frame_url = last_frame["image_url"]
   ```

3. 需要修改：
   - `app/services/storyboard.py` - 分镜生成逻辑
   - `app/schemas/storyboard.py` - Shot schema（添加 `last_frame_url` 字段）

---

## ✅ 当前状态总结

### 已经支持的

- ✅ 后端API完全支持 `last_frame_url` 参数
- ✅ 豆包 provider 支持首尾帧模式
- ✅ 手动测试可以通过前端或API调用

### 需要手动做的

- ⚠️ 准备尾帧图片（手动生成）
- ⚠️ 在 shots_data 中添加 `last_frame_url` 字段（手动修改）

### 未来可以自动化

- 🚀 分镜生成时自动生成尾帧图片
- 🚀 智能识别需要过渡的镜头
- 🚀 前端UI支持尾帧选择/上传

---

## 🚀 现在就可以测试！

**最简单的测试方法**：

1. **启动系统**
   ```bash
   python start.py
   ```

2. **在网页上生成分镜**
   - 正常流程，生成图片和视频

3. **选择一个镜头测试**
   - 复制这个镜头的首帧图片
   - 重命名为 `xxx_endframe.png`
   - 在前端代码中添加 `last_frame_url` 字段

4. **重新生成视频**
   - 观察双帧过渡效果

---

## 💡 测试建议

### 第一次测试

**建议测试最简单的场景**：
- 首帧：人物站立
- 尾帧：人物坐着
- Prompt："从站立到坐下"

这样可以快速验证功能是否正常。

---

### 如果测试成功

**可以考虑**：
1. 更新文档，推翻之前的结论
2. 在前端添加尾帧选择功能
3. 实现自动生成尾帧的逻辑
4. 在分镜生成时智能判断是否需要尾帧

---

**现在可以启动 `start.py` 开始测试了！** 🎉

如果有任何问题或需要帮助，随时告诉我！
