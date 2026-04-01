<template>
  <div class="scene-stream">
    <div v-for="ep in scenes" :key="ep.episode" class="episode-card">
      <div class="ep-header">
        <span class="ep-badge">第 {{ ep.episode }} 集</span>
        <span class="ep-title">{{ ep.title }}</span>
      </div>
      <div v-if="enableSceneKeyArt" class="scene-key-art-panel">
        <div class="scene-key-art-header">
          <div>
            <div class="scene-key-art-title">本集共享环境图组</div>
            <div class="scene-key-art-subtitle">同集相似场景共用一组图，每组只生成一张主场景参考图，差异大的场景会额外拆组</div>
          </div>
          <span class="scene-key-art-status" :class="assetStatusClass(getEpisodeStatus(ep.episode))">
            {{ assetStatusLabel(getEpisodeStatus(ep.episode)) }}
          </span>
        </div>
        <div v-if="getEpisodeGroups(ep.episode).length" class="scene-key-art-group-list">
          <div
            v-for="group in getEpisodeGroups(ep.episode)"
            :key="group.environment_pack_key"
            class="scene-key-art-group"
          >
            <div class="scene-key-art-group-top">
              <div>
                <div class="scene-key-art-group-title">{{ group.group_label || '环境组' }}</div>
                <div class="scene-key-art-group-copy">
                  覆盖场景：{{ formatSceneNumbers(group.affected_scene_numbers) }} · {{ group.summary_environment || '主环境' }}
                </div>
              </div>
            </div>
            <div class="scene-key-art-grid">
              <div
                class="scene-key-art-card"
                :class="{ ready: !!group.variants?.scene }"
              >
                <img
                  v-if="group.variants?.scene?.image_url"
                  :src="resolveAssetImageUrl(group.variants.scene.image_url)"
                  :alt="buildSceneReferenceAlt(group)"
                  class="scene-key-art-image"
                />
                <div v-else class="scene-key-art-placeholder">Scene Reference</div>
                <div class="scene-key-art-meta">
                  <span class="scene-key-art-label">主场景参考图</span>
                  <span class="scene-key-art-pill">scene</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="scene-key-art-empty">
          还没有生成环境组。点击下方按钮后，会按同集场景环境自动拆成 1 组或多组。
        </div>
        <div class="scene-key-art-actions">
          <button
            class="scene-key-art-btn"
            :disabled="getEpisodeStatus(ep.episode) === 'loading'"
            @click="$emit('generate-scene-key-art', { episode: ep.episode, scene: getEpisodeRepresentativeScene(ep) })"
          >
            {{ getEpisodeGroups(ep.episode).length ? '重新生成本集环境图组' : '生成本集环境图组' }}
          </button>
          <span v-if="getEpisodeError(ep.episode)" class="scene-key-art-error">
            {{ getEpisodeError(ep.episode) }}
          </span>
        </div>
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
import { useSettingsStore } from '../stores/settings.js'
import { getSceneKey } from '../stores/story.js'
import { resolveBackendMediaUrl } from '../utils/backend.js'

const props = defineProps({
  scenes: {
    type: Array,
    default: () => [],
  },
  streaming: Boolean,
  enableSceneKeyArt: Boolean,
  sceneReferenceAssets: {
    type: Object,
    default: () => ({}),
  },
})

defineEmits(['generate-scene-key-art'])

const settings = useSettingsStore()

function getSceneAsset(episode, sceneNumber) {
  return props.sceneReferenceAssets[getSceneKey(episode, sceneNumber)] || {
    status: 'idle',
    variants: {},
    error: '',
  }
}

function getEpisodeRepresentativeScene(episode) {
  return episode?.scenes?.[0] || { scene_number: 1 }
}

function getEpisodeAsset(episodeNumber) {
  const episode = props.scenes.find(item => item.episode === episodeNumber)
  const representativeScene = getEpisodeRepresentativeScene(episode)
  return getSceneAsset(episodeNumber, representativeScene.scene_number)
}

function getEpisodeGroups(episodeNumber) {
  const episode = props.scenes.find(item => item.episode === episodeNumber)
  const sceneKeys = (episode?.scenes || []).map(scene => getSceneKey(episodeNumber, scene.scene_number))
  const groups = []
  const seen = new Set()
  sceneKeys.forEach(sceneKey => {
    const asset = props.sceneReferenceAssets[sceneKey]
    const packKey = asset?.environment_pack_key
    if (!asset || !packKey || seen.has(packKey)) return
    seen.add(packKey)
    groups.push(asset)
  })
  return groups.sort((left, right) => (left.group_index || 0) - (right.group_index || 0))
}

function getEpisodeStatus(episodeNumber) {
  const groups = getEpisodeGroups(episodeNumber)
  if (groups.some(group => group.status === 'loading')) return 'loading'
  if (groups.some(group => group.status === 'failed')) return 'failed'
  if (groups.some(group => group.status === 'stale')) return 'stale'
  if (groups.some(group => group.status === 'idle')) return 'idle'
  if (groups.length > 0 && groups.every(group => group.status === 'ready')) return 'ready'
  return getEpisodeAsset(episodeNumber).status || 'idle'
}

function getEpisodeError(episodeNumber) {
  const groups = getEpisodeGroups(episodeNumber)
  return groups.find(group => group.error)?.error || getEpisodeAsset(episodeNumber).error || ''
}

function buildSceneReferenceAlt(group = {}) {
  const label = group.group_name || group.group_label || group.variants?.scene?.name || group.summary_environment || '环境组'
  return `${label} 主场景参考图`
}

function formatSceneNumbers(numbers = []) {
  return numbers.length ? numbers.map(number => String(number).padStart(2, '0')).join(' / ') : '--'
}

function assetStatusLabel(status) {
  return {
    idle: '未生成',
    loading: '生成中',
    ready: '已就绪',
    failed: '失败',
    stale: '需刷新',
  }[status] || '未生成'
}

function assetStatusClass(status) {
  return status || 'idle'
}

function resolveAssetImageUrl(url) {
  return resolveBackendMediaUrl(url, settings.backendUrl)
}
</script>

<style scoped src="../style/components/scenestream.css"></style>
