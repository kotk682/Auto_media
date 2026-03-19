<template>
  <div class="scene-stream">
    <div v-for="ep in scenes" :key="ep.episode" class="episode-card">
      <div class="ep-header">
        <span class="ep-badge">第 {{ ep.episode }} 集</span>
        <span class="ep-title">{{ ep.title }}</span>
      </div>
      <div class="scenes">
        <div v-for="scene in ep.scenes" :key="scene.scene_number" class="scene-block">
          <div class="scene-num">场景 {{ String(scene.scene_number).padStart(2, '0') }}</div>
          <div class="scene-row">
            <span class="scene-tag">【环境】</span>
            <span class="scene-text">{{ scene.environment }}</span>
          </div>
          <div class="scene-row">
            <span class="scene-tag">【画面】</span>
            <span class="scene-text">{{ scene.visual }}</span>
          </div>
          <div class="audio-block">
            <div v-for="(a, i) in scene.audio" :key="i" class="audio-line">
              <span class="character">{{ a.character }}</span>
              <span class="line">{{ a.line }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="streaming" class="streaming-indicator">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      正在生成...
    </div>
  </div>
</template>

<script setup>
defineProps({ scenes: Array, streaming: Boolean })
</script>

<style scoped>
.scene-stream { display: flex; flex-direction: column; gap: 16px; }
.episode-card {
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  animation: fadeIn 0.4s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.ep-header {
  background: #6c63ff;
  color: #fff;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.ep-badge {
  background: rgba(255,255,255,0.2);
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
}
.ep-title { font-weight: 600; font-size: 15px; }
.scenes { padding: 14px 16px; display: flex; flex-direction: column; gap: 20px; }
.scene-block {
  border-left: 3px solid #e0e0e0;
  padding-left: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.scene-num { font-size: 11px; font-weight: 700; color: #aaa; letter-spacing: 1px; margin-bottom: 2px; }
.scene-row { display: flex; gap: 6px; font-size: 13px; line-height: 1.6; }
.scene-tag { color: #6c63ff; font-weight: 700; white-space: nowrap; font-size: 12px; padding-top: 1px; }
.scene-text { color: #444; }
.audio-block {
  margin-top: 6px;
  background: #f8f7ff;
  border-radius: 8px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.audio-line { display: flex; gap: 8px; font-size: 13px; }
.character { color: #6c63ff; font-weight: 600; white-space: nowrap; }
.line { color: #333; line-height: 1.5; }
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #999;
  font-size: 14px;
  padding: 8px 0;
}
.dot { width: 6px; height: 6px; background: #6c63ff; border-radius: 50%; animation: bounce 1s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1.2); opacity: 1; }
}
</style>
