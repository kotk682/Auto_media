<template>
  <div class="art-style-selector">
    <!-- 折叠头 -->
    <button class="collapse-header" @click="expanded = !expanded">
      <span class="header-left">
        <span class="icon">🎨</span>
        <span class="label">画风设定</span>
        <span class="style-badge" :class="{ empty: !store.artStyle }">{{ confirmedPresetName || '写实摄影（默认）' }}</span>
      </span>
      <span class="chevron" :class="{ open: expanded }">›</span>
    </button>

    <!-- 展开内容 -->
    <div v-if="expanded" class="collapse-body">
      <!-- 预设 chips -->
      <div class="chips-row">
        <button
          v-for="preset in PRESETS"
          :key="preset.id"
          class="chip"
          :class="{ active: selectedPresetId === preset.id }"
          @click="selectPreset(preset)"
        >{{ preset.icon }} {{ preset.name }}</button>
      </div>
      <!-- 输入框 -->
      <div class="input-row">
        <input
          v-model="localStyle"
          class="style-input"
          placeholder="或直接输入画风描述…"
          @input="onTextInput"
        />
        <button v-if="localStyle" class="clear-btn" @click="clearStyle">✕</button>
      </div>
      <!-- 确认行 -->
      <div class="confirm-row">
        <span v-if="saved" class="saved-hint">✓ 已保存</span>
        <span v-if="saveError" class="error-hint">{{ saveError }}</span>
        <button
          class="confirm-btn"
          :disabled="localStyle === (store.artStyle || DEFAULT_ART_STYLE_PROMPT)"
          @click="confirmStyle"
        >确认</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useStoryStore } from '../stores/story.js'
import { patchStory } from '../api/story.js'
import { ART_STYLE_PRESETS, DEFAULT_ART_STYLE_PRESET, DEFAULT_ART_STYLE_PROMPT } from '../constants/artStylePresets.js'

const store = useStoryStore()
const PRESETS = ART_STYLE_PRESETS

const expanded = ref(false)
const selectedPresetId = ref(null)
const localStyle = ref('')
const saved = ref(false)
const saveError = ref('')

/** 已确认保存的 preset 名（根据 store 中的值） */
const confirmedPresetName = computed(() => {
  const foundPreset = PRESETS.find(preset => preset.prompt === (store.artStyle || DEFAULT_ART_STYLE_PROMPT))
  return foundPreset ? foundPreset.name : null
})

onMounted(() => {
  localStyle.value = store.artStyle || DEFAULT_ART_STYLE_PROMPT
  const match = PRESETS.find(p => p.prompt === localStyle.value)
  selectedPresetId.value = match ? match.id : DEFAULT_ART_STYLE_PRESET?.id || null
})

/** 点击预设：只更新本地状态，不写入 store */
function selectPreset(preset) {
  if (selectedPresetId.value === preset.id) {
    selectedPresetId.value = DEFAULT_ART_STYLE_PRESET?.id || null
    localStyle.value = DEFAULT_ART_STYLE_PROMPT
  } else {
    selectedPresetId.value = preset.id
    localStyle.value = preset.prompt
  }
}

/** 输入框输入：只更新本地状态 */
function onTextInput() {
  const match = PRESETS.find(p => p.prompt === localStyle.value)
  selectedPresetId.value = match ? match.id : null
}

/** 清除：立即清空并持久化 */
async function clearStyle() {
  const previousState = {
    localStyle: localStyle.value,
    selectedPresetId: selectedPresetId.value,
    artStyle: store.artStyle,
    saved: saved.value,
    expanded: expanded.value,
  }
  saveError.value = ''
  localStyle.value = DEFAULT_ART_STYLE_PROMPT
  selectedPresetId.value = DEFAULT_ART_STYLE_PRESET?.id || null
  store.setArtStyle('')
  if (store.storyId) {
    try {
      const result = await patchStory(store.storyId, { art_style: '' })
      if (!result) throw new Error('patchStory returned no result')
    } catch (error) {
      console.error('Failed to clear art style:', error)
      localStyle.value = previousState.localStyle
      selectedPresetId.value = previousState.selectedPresetId
      store.setArtStyle(previousState.artStyle)
      saved.value = previousState.saved
      expanded.value = previousState.expanded
      saveError.value = '清除失败，请重试'
    }
  }
}

/** 确认：写入 store（localStorage）并持久化到后端 */
async function confirmStyle() {
  const previousState = {
    localStyle: localStyle.value,
    selectedPresetId: selectedPresetId.value,
    artStyle: store.artStyle,
    saved: saved.value,
    expanded: expanded.value,
  }
  saveError.value = ''
  store.setArtStyle(localStyle.value)
  localStyle.value = store.artStyle
  const match = PRESETS.find(preset => preset.prompt === localStyle.value)
  selectedPresetId.value = match ? match.id : null
  try {
    if (store.storyId) {
      const result = await patchStory(store.storyId, { art_style: store.artStyle })
      if (!result) throw new Error('patchStory returned no result')
    }
  } catch (error) {
    console.error('Failed to persist art style:', error)
    localStyle.value = previousState.localStyle
    selectedPresetId.value = previousState.selectedPresetId
    store.setArtStyle(previousState.artStyle)
    saved.value = previousState.saved
    expanded.value = previousState.expanded
    saveError.value = '保存失败，请重试'
    return
  }
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
  expanded.value = false
}

watch(() => store.artStyle, (val) => {
  const effectiveStyle = val || DEFAULT_ART_STYLE_PROMPT
  if (effectiveStyle !== localStyle.value) {
    localStyle.value = effectiveStyle
    const match = PRESETS.find(p => p.prompt === effectiveStyle)
    selectedPresetId.value = match ? match.id : DEFAULT_ART_STYLE_PRESET?.id || null
  }
})
</script>

<style scoped src="../style/components/artstyleselector.css"></style>
