<template>
  <div class="page">
    <StepIndicator :current="3" :loading="streaming" />
    <div class="content">
      <div class="title-row">
        <div>
          <h1>剧本生成</h1>
          <p class="subtitle">确认大纲后开始生成完整剧本</p>
        </div>
      </div>

      <div class="top-row">
        <div class="outline-col">
          <OutlinePreview
            v-if="store.meta"
            :meta="store.meta"
            :characters="store.characters"
            :outline="store.outline"
          />
        </div>
        <div class="graph-col">
          <CharacterGraph
            v-if="store.characters.length"
            :characters="store.characters"
            :relationships="store.relationships"
          />
          <ArtStyleSelector />
          <CharacterDesign
            v-if="store.characters.length"
            :characters="store.characters"
          />
        </div>
      </div>

      <div v-if="showResumeActionRow" class="generate-action-row">
        <button
          class="continue-btn"
          type="button"
          :disabled="!store.meta || nextIncompleteEpisode == null"
          :title="resumeButtonHint"
          @click="startContinueGenerate"
        >
          {{ continueButtonLabel }}
        </button>
        <button
          class="generate-btn generate-btn-secondary"
          :disabled="!store.meta"
          @click="startGenerate"
        >
          重新生成全部 ✨
        </button>
      </div>

      <div
        v-else-if="canGenerate"
        class="generate-btn-wrapper"
      >
        <button
          class="generate-btn"
          :disabled="!store.meta"
          @click="startGenerate"
        >
          {{ generateButtonLabel }}
        </button>
      </div>

      <div
        v-if="showResumeActionRow"
        class="resume-hint"
        role="status"
        aria-live="polite"
      >
        {{ resumeButtonHint }}
      </div>

      <div v-if="error && !streaming && !hasSceneOutput" class="error-tip" role="alert" aria-live="assertive">{{ error }}</div>

      <div v-if="streaming || hasSceneOutput" class="script-section">
        <h2>剧本</h2>
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
        <SceneStream :scenes="currentEpisodeScenes" :streaming="streaming" />
        <div v-if="error" class="error-tip" role="alert" aria-live="assertive">{{ error }}</div>
        <div
          v-else-if="showIncompleteScriptTip"
        class="error-tip"
        role="alert"
        aria-live="assertive"
      >
          {{ showResumeActionRow ? '当前剧本不完整，可继续生成或重新生成全部。' : '当前剧本不完整，请重新生成。' }}
        </div>
      </div>

      <div v-if="done" class="btn-row">
        <button class="back-btn" @click="router.push('/step2')">← 返回</button>
        <button class="next-btn" @click="router.push('/step4')">预览导出 →</button>
      </div>
    </div>
  </div>
  <ApiKeyModal
    :show="showKeyModal"
    :type="keyModalType"
    :title="keyModalType === 'invalid' ? 'API Key 错误' : '未设置 API Key'"
    :message="keyModalMsg || '请先前往设置页填入 API Key，才能生成剧本。'"
    @close="showKeyModal = false"
  />
  <OutlineChatPanel :show="chatOpen" @close="chatOpen = false" />
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import StepIndicator from '../components/StepIndicator.vue'
import OutlinePreview from '../components/OutlinePreview.vue'
import SceneStream from '../components/SceneStream.vue'
import CharacterGraph from '../components/CharacterGraph.vue'
import CharacterDesign from '../components/CharacterDesign.vue'
import ApiKeyModal from '../components/ApiKeyModal.vue'
import OutlineChatPanel from '../components/OutlineChatPanel.vue'
import ArtStyleSelector from '../components/ArtStyleSelector.vue'
import { useStoryStore } from '../stores/story.js'
import { streamScript } from '../api/story.js'
import { canAccessStep, getStepRedirectPath } from '../utils/stepAccess.js'
import { formatEpisodeList, getIncompleteScriptEpisodes, hasCompleteGeneratedScript } from '../utils/scriptValidation.js'

const router = useRouter()
const store = useStoryStore()
const streaming = ref(false)
const error = ref('')
const chatOpen = ref(false)
const showKeyModal = ref(false)
const keyModalType = ref('missing')
const keyModalMsg = ref('')
const currentEpisodeIndex = ref(0)
const userPinnedEpisode = ref(false)
const hasSceneOutput = computed(() => store.scenes.length > 0)
const generatedEpisodeNumbers = computed(() => store.scenes
  .filter(episode => Array.isArray(episode?.scenes) && episode.scenes.length > 0)
  .map(episode => {
    const parsed = Number.parseInt(String(episode?.episode ?? '').trim(), 10)
    return Number.isInteger(parsed) ? parsed : null
  })
  .filter(episode => episode != null)
  .sort((left, right) => left - right))
const lastGeneratedEpisode = computed(() => (
  generatedEpisodeNumbers.value.length > 0
    ? generatedEpisodeNumbers.value[generatedEpisodeNumbers.value.length - 1]
    : null
))
const hasValidScript = computed(() => hasCompleteGeneratedScript({
  outline: store.outline,
  scenes: store.scenes,
}))
const incompleteEpisodes = computed(() => getIncompleteScriptEpisodes({
  outline: store.outline,
  scenes: store.scenes,
}))
const nextIncompleteEpisode = computed(() => incompleteEpisodes.value[0] ?? null)
const done = computed(() => store.step3Done && hasValidScript.value)
const canGenerate = computed(() => !streaming.value)
const generateButtonLabel = computed(() => (hasSceneOutput.value ? '重新生成剧本 ✨' : '开始生成剧本 ✨'))
const showResumeActionRow = computed(() => (
  canGenerate.value
  && hasSceneOutput.value
  && !hasValidScript.value
  && nextIncompleteEpisode.value != null
))
const continueButtonLabel = computed(() => (
  nextIncompleteEpisode.value != null
    ? `继续生成（第 ${nextIncompleteEpisode.value} 集起）`
    : '继续生成'
))
const resumeButtonHint = computed(() => (
  nextIncompleteEpisode.value != null
    ? lastGeneratedEpisode.value != null
      ? `当前已保留到第 ${lastGeneratedEpisode.value} 集，可从第 ${nextIncompleteEpisode.value} 集继续生成；如需全部重做，也可以重新生成全部。`
      : `当前剧本在第 ${nextIncompleteEpisode.value} 集中断，可从该集继续生成。`
    : '当前剧本不完整，可继续生成或重新生成全部。'
))
const showIncompleteScriptTip = computed(() => (
  !streaming.value
  && hasSceneOutput.value
  && !hasValidScript.value
  && !error.value
))
const episodeCount = computed(() => store.scenes.length)
const currentEpisode = computed(() => store.scenes[currentEpisodeIndex.value] || null)
const currentEpisodeScenes = computed(() => (currentEpisode.value ? [currentEpisode.value] : []))
const canGoPrev = computed(() => currentEpisodeIndex.value > 0)
const canGoNext = computed(() => currentEpisodeIndex.value < episodeCount.value - 1)

let scriptAbortController = null
onUnmounted(() => { scriptAbortController?.abort() })
onMounted(() => {
  if (!canAccessStep(store, 3)) {
    router.replace(getStepRedirectPath(store, 3))
    return
  }
})

watch(
  () => store.scenes.length,
  (nextLength, previousLength = 0) => {
    if (!nextLength) {
      currentEpisodeIndex.value = 0
      userPinnedEpisode.value = false
      return
    }

    const shouldFollowLatest =
      !userPinnedEpisode.value ||
      previousLength === 0 ||
      currentEpisodeIndex.value >= previousLength - 1

    if (shouldFollowLatest) {
      currentEpisodeIndex.value = nextLength - 1
      return
    }

    currentEpisodeIndex.value = Math.min(currentEpisodeIndex.value, nextLength - 1)
  },
  { immediate: true }
)

function isAuthError(msg) {
  return /401|403|invalid|incorrect|unauthorized|api.?key/i.test(msg)
}

function buildResumeErrorHint() {
  if (!store.scenes.length || nextIncompleteEpisode.value == null) return ''
  if (lastGeneratedEpisode.value != null) {
    return `已保留到第 ${lastGeneratedEpisode.value} 集，可从第 ${nextIncompleteEpisode.value} 集继续生成`
  }
  return `已保留已成功集数，可从第 ${nextIncompleteEpisode.value} 集继续生成`
}

function setScriptGenerationError(message) {
  store.setStep(3)
  store.step3Done = false
  const normalizedMessage = String(message || '生成失败，请重试').trim()
  const resumeHint = buildResumeErrorHint()
  error.value = resumeHint ? `${normalizedMessage}，${resumeHint}` : normalizedMessage
}

async function runGenerate({ resumeFromEpisode = null } = {}) {
  scriptAbortController?.abort()
  const controller = new AbortController()
  scriptAbortController = controller
  const isResumeGeneration = Number.isInteger(resumeFromEpisode)
  streaming.value = true
  error.value = ''
  userPinnedEpisode.value = false
  store.setStep(3)
  if (isResumeGeneration) {
    store.retainScenesBeforeEpisode(resumeFromEpisode)
    currentEpisodeIndex.value = Math.max(store.scenes.length - 1, 0)
  } else {
    currentEpisodeIndex.value = 0
    store.resetScenes()
  }
  try {
    await streamScript(
      store.storyId,
      (scene) => store.addScene(scene),
      () => {
        const isCompleteScript = hasCompleteGeneratedScript({
          outline: store.outline,
          scenes: store.scenes,
        })
        if (!isCompleteScript) {
          const incompleteEpisodes = getIncompleteScriptEpisodes({
            outline: store.outline,
            scenes: store.scenes,
          })
          const message = incompleteEpisodes.length > 0
            ? `剧本生成不完整：${formatEpisodeList(incompleteEpisodes)} 未生成有效场景`
            : '剧本生成失败：当前故事缺少大纲或返回结果结构无效，请重试'
          setScriptGenerationError(message)
          return
        }
        error.value = ''
        store.step3Done = true
        store.setStep(4)
      },
      (msg) => {
        const normalizedMessage = msg || '生成失败，请重试'
        setScriptGenerationError(normalizedMessage)
        if (isAuthError(msg)) {
          keyModalType.value = 'invalid'
          keyModalMsg.value = 'API Key 无效或已过期，请检查后重新设置。'
          showKeyModal.value = true
        }
      },
      controller.signal,
      isResumeGeneration ? { resumeFromEpisode } : {}
    )
  } finally {
    streaming.value = false
    if (scriptAbortController === controller) {
      scriptAbortController = null
    }
  }
}

async function startGenerate() {
  await runGenerate()
}

async function startContinueGenerate() {
  if (nextIncompleteEpisode.value == null) return
  await runGenerate({ resumeFromEpisode: nextIncompleteEpisode.value })
}

function goPrevEpisode() {
  if (!canGoPrev.value) return
  currentEpisodeIndex.value -= 1
  userPinnedEpisode.value = true
}

function goNextEpisode() {
  if (!canGoNext.value) return
  currentEpisodeIndex.value += 1
  userPinnedEpisode.value = currentEpisodeIndex.value < episodeCount.value - 1
}
</script>

<style scoped src="../style/step3script.css"></style>
