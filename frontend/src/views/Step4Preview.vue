<template>
  <div class="page">
    <StepIndicator :current="4" :loading="false" />
    <div class="content">
      <h1>预览 & 导出</h1>
      <p class="subtitle">你的短剧剧本已生成完毕</p>

      <div v-if="store.meta" class="summary-card">
        <div class="summary-title">{{ store.meta.title }}</div>
        <div class="summary-stats">
          <span>{{ store.meta.episodes }} 集</span>
          <span>{{ store.characters.length }} 个角色</span>
          <span>{{ totalScenes }} 个场景</span>
          <span>{{ readyEpisodeKeyArtCount }}/{{ store.scenes.length }} 集环境图组</span>
        </div>
      </div>

      <div v-if="episodeCount" class="episode-slider">
        <button
          class="episode-nav-btn"
          :disabled="!canGoPrev"
          @click="goPrevEpisode"
        >
          ←
        </button>
        <div class="episode-slider-center">
          <div class="episode-slider-label">第 {{ currentEpisode?.episode }} 集 / 共 {{ episodeCount }} 集</div>
          <div class="episode-slider-title">{{ currentEpisode?.title || '未命名剧集' }}</div>
        </div>
        <button
          class="episode-nav-btn"
          :disabled="!canGoNext"
          @click="goNextEpisode"
        >
          →
        </button>
      </div>

      <SceneStream
        :scenes="currentEpisodeScenes"
        :streaming="false"
        :enable-scene-key-art="true"
        :scene-reference-assets="store.sceneReferenceAssets"
        @generate-scene-key-art="handleGenerateSceneKeyArt"
      />

      <div class="export-section">
        <ExportPanel />
        <button class="video-btn" @click="generateVideo">
          场景分镜
        </button>
        <button class="restart-btn" @click="restart">重新创作</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StepIndicator from '../components/StepIndicator.vue'
import SceneStream from '../components/SceneStream.vue'
import ExportPanel from '../components/ExportPanel.vue'
import { generateEpisodeSceneReference } from '../api/story.js'
import { useStoryStore } from '../stores/story.js'

const router = useRouter()
const store = useStoryStore()
const currentEpisodeIndex = ref(0)

onMounted(() => {
  if (!store.meta || !store.scenes.length) router.replace('/step1')
  store.ensureSceneReferenceAssets()
})

const episodeCount = computed(() => store.scenes.length)
const currentEpisode = computed(() => store.scenes[currentEpisodeIndex.value] || null)
const currentEpisodeScenes = computed(() => (currentEpisode.value ? [currentEpisode.value] : []))
const canGoPrev = computed(() => currentEpisodeIndex.value > 0)
const canGoNext = computed(() => currentEpisodeIndex.value < episodeCount.value - 1)

const totalScenes = computed(() =>
  store.scenes.reduce((sum, s) => sum + s.scenes.length, 0)
)

const readyEpisodeKeyArtCount = computed(() =>
  store.scenes.filter(episode => store.getEpisodeSceneReferenceStatus(episode.episode) === 'ready').length
)

async function handleGenerateSceneKeyArt({ episode, scene }) {
  store.setEpisodeSceneReferenceStatus(episode, 'loading', '')
  try {
    const forceRegenerate = store.getEpisodeSceneReferenceGroups(episode).length > 0
    const result = await generateEpisodeSceneReference(store.storyId, episode, { forceRegenerate })
    store.applyEpisodeSceneReferenceAsset(result)
  } catch (error) {
    store.setEpisodeSceneReferenceStatus(episode, 'failed', error.message || '环境图生成失败')
  }
}

function generateVideo() {
  router.push('/video-generation')
}

function restart() {
  store.$reset()
  router.push('/step1')
}

function goPrevEpisode() {
  if (!canGoPrev.value) return
  currentEpisodeIndex.value -= 1
}

function goNextEpisode() {
  if (!canGoNext.value) return
  currentEpisodeIndex.value += 1
}
</script>

<style scoped>
.page { min-height: 100vh; background: #f5f5f7; padding: 32px 16px; }
.content { max-width: 600px; margin: 32px auto 0; }
h1 { font-size: 26px; font-weight: 700; margin-bottom: 6px; }
.subtitle { color: #888; margin-bottom: 24px; }
.episode-slider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #ffffff, #f3f1ff);
  border: 1px solid #e8e3ff;
}
.episode-slider-center {
  flex: 1;
  min-width: 0;
  text-align: center;
}
.episode-slider-label {
  font-size: 12px;
  font-weight: 700;
  color: #6c63ff;
  letter-spacing: 0.04em;
}
.episode-slider-title {
  margin-top: 4px;
  color: #2d2d38;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.episode-nav-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #6c63ff;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  transition: transform 0.2s, opacity 0.2s, background 0.2s;
}
.episode-nav-btn:hover:not(:disabled) {
  background: #5a52e0;
  transform: translateY(-1px);
}
.episode-nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.summary-card {
  background: linear-gradient(135deg, #6c63ff, #a78bfa);
  color: #fff;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 24px;
}
.summary-title { font-size: 20px; font-weight: 700; margin-bottom: 12px; }
.summary-stats { display: flex; gap: 16px; }
.summary-stats span {
  background: rgba(255,255,255,0.2);
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 13px;
}
.export-section {
  display: flex;
  gap: 12px;
  margin-top: 28px;
  align-items: center;
}
.video-btn {
  padding: 12px 20px;
  background: #6c63ff;
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  border: none;
  cursor: pointer;
}
.video-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.video-btn:not(:disabled):hover { background: #5a52e0; }
.restart-btn {
  padding: 12px 20px;
  background: #fff;
  color: #555;
  border-radius: 10px;
  font-size: 14px;
  border: 2px solid #e0e0e0;
}
.restart-btn:hover { border-color: #6c63ff; color: #6c63ff; }

@media (max-width: 768px) {
  .episode-slider {
    padding: 12px;
    gap: 10px;
  }

  .episode-slider-title {
    font-size: 14px;
  }

  .episode-nav-btn {
    width: 38px;
    height: 38px;
  }
}
</style>
