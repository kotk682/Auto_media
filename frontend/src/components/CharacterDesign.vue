<template>
  <div class="character-design-section">
    <div class="section-header">
      <h3>角色人设图</h3>
      <button class="generate-all-btn" @click="generateAll" :disabled="anyLoading">
        {{ isGenerating ? '生成中...' : '生成全部' }}
      </button>
    </div>

    <div class="carousel-container">
      <button class="nav-btn prev" @click="prev" :disabled="currentIndex === 0">
        ‹
      </button>

      <div class="carousel-viewport">
        <div class="carousel-track" :style="{ transform: `translateX(-${currentIndex * 100}%)` }">
          <div
            v-for="char in characters"
            :key="char.id || char.name"
            class="character-slide"
          >
            <div class="slide-content">
              <div class="card-image-area">
                <!-- 角色信息覆盖在图片上 -->
                <div class="image-overlay-header">
                  <span class="char-name">{{ char.name }}</span>
                  <span class="char-role">{{ char.role }}</span>
                </div>

                <div v-if="!getCharacterData(char).imageUrl" class="placeholder-image">
                  <span>待生成</span>
                </div>
                <img
                  v-else
                  :src="getMediaUrl(getCharacterData(char).imageUrl)"
                  :alt="char.name"
                  class="character-image"
                  @click="openPreview(char)"
                />

                <!-- 底部操作栏覆盖在图片上 -->
                <div class="image-overlay-footer">
                  <button
                    class="generate-btn"
                    @click="generateOne(char)"
                    :disabled="anyLoading"
                  >
                    {{ getCharacterData(char).loading ? '生成中...' : (getCharacterData(char).imageUrl ? '重新生成' : '生成人设') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <button class="nav-btn next" @click="next" :disabled="currentIndex >= characters.length - 1">
        ›
      </button>

      <div class="carousel-indicators">
        <span
          v-for="(_, i) in characters"
          :key="i"
          class="indicator"
          :class="{ active: i === currentIndex }"
          @click="goTo(i)"
        ></span>
      </div>
    </div>
  </div>

  <div v-if="error" class="error-tip">{{ error }}</div>

  <div
    v-if="previewImageUrl"
    class="image-preview-modal"
    @click.self="closePreview"
  >
    <div class="image-preview-dialog">
      <button type="button" class="image-preview-close" @click="closePreview">×</button>
      <img :src="previewImageUrl" :alt="previewCharacterName || '角色人设图预览'" class="image-preview-full" />
    </div>
  </div>

  <ApiKeyModal
    :show="showKeyModal"
    :type="keyModalType"
    :title="keyModalType === 'invalid' ? 'API Key 无效' : 'API Key 未设置'"
    :message="keyModalMsg"
    @close="showKeyModal = false"
  />
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useStoryStore } from '../stores/story.js'
import { useSettingsStore } from '../stores/settings.js'
import { generateCharacterImage, generateAllCharacterImages, getCharacterImages } from '../api/story.js'
import ApiKeyModal from './ApiKeyModal.vue'
import { resolveBackendMediaUrl } from '../utils/backend.js'
import { findCharacterByRef, findCharacterImageEntry, getCharacterKey } from '../utils/character.js'

const props = defineProps({
  characters: {
    type: Array,
    default: () => []
  }
})

const store = useStoryStore()
const settings = useSettingsStore()

function getMediaUrl(path) {
  return resolveBackendMediaUrl(path, settings.backendUrl)
}

const currentIndex = ref(0)
const isGenerating = ref(false)
const characterData = reactive({})
const error = ref('')
const showKeyModal = ref(false)
const keyModalType = ref('missing')
const keyModalMsg = ref('')
const previewImageUrl = ref('')
const previewCharacterName = ref('')

function isAuthError(msg) {
  return /401|403|invalid|incorrect|unauthorized|api.?key/i.test(msg)
}

function handleError(msg) {
  if (isAuthError(msg)) {
    keyModalType.value = 'invalid'
    keyModalMsg.value = 'API Key 无效或已过期，请检查后重新设置。'
    showKeyModal.value = true
  } else {
    error.value = msg || '生成失败，请重试'
  }
}

const anyLoading = computed(() =>
  isGenerating.value || Object.values(characterData).some(d => d.loading)
)

function getCharacterData(character) {
  const key = typeof character === 'string' ? character : getCharacterKey(character)
  if (!key) return { imageUrl: null, loading: false }
  if (!characterData[key]) {
    characterData[key] = { imageUrl: null, loading: false }
  }
  return characterData[key]
}

function resetCharacterData() {
  for (const key of Object.keys(characterData)) {
    delete characterData[key]
  }
  currentIndex.value = 0
}

function prev() {
  if (currentIndex.value > 0) {
    currentIndex.value--
  }
}

function next() {
  if (currentIndex.value < props.characters.length - 1) {
    currentIndex.value++
  }
}

function goTo(index) {
  currentIndex.value = index
}

function openPreview(char) {
  const imageUrl = getCharacterData(char).imageUrl
  if (!imageUrl) return
  previewImageUrl.value = getMediaUrl(imageUrl)
  previewCharacterName.value = char?.name || ''
}

function closePreview() {
  previewImageUrl.value = ''
  previewCharacterName.value = ''
}

function handleKeydown(event) {
  if (event.key === 'Escape' && previewImageUrl.value) {
    closePreview()
  }
}

async function generateOne(char) {
  if (!char || !store.storyId) return
  if (!char.id) {
    error.value = `角色「${char.name || '未命名'}」缺少 ID，已阻止按名字复用人设图`
    return
  }

  const key = getCharacterKey(char)
  const data = getCharacterData(key)
  data.loading = true

  try {
    const result = await generateCharacterImage(store.storyId, char)
    data.imageUrl = result.image_url
    store.characterImages = {
      ...(store.characterImages || {}),
      [result.character_id || key]: {
        ...(store.characterImages?.[result.character_id || key] || {}),
        image_url: result.image_url,
        prompt: result.prompt,
        character_id: result.character_id || char.id || '',
        character_name: char.name,
      },
    }
    error.value = ''
  } catch (e) {
    console.error('Failed to generate character image:', e)
    handleError(e.message)
  } finally {
    data.loading = false
  }
}

async function generateAll() {
  if (!store.storyId || props.characters.length === 0) return

  isGenerating.value = true

  for (const char of props.characters) {
    getCharacterData(char).loading = true
  }

  try {
    const { results, errors } = await generateAllCharacterImages(store.storyId, props.characters)
    const nextCharacterImages = { ...(store.characterImages || {}) }
    for (const result of results) {
      const char = findCharacterByRef(props.characters, {
        id: result.character_id,
      })
      const key = result.character_id || getCharacterKey(char)
      if (!key) continue
      const data = getCharacterData(key)
      data.imageUrl = result.image_url
      data.loading = false
      nextCharacterImages[key] = {
        ...(nextCharacterImages[key] || {}),
        image_url: result.image_url,
        prompt: result.prompt,
        character_id: result.character_id || char?.id || '',
        character_name: char?.name || result.character_name,
      }
    }
    store.characterImages = nextCharacterImages
    if (errors && errors.length > 0) {
      const names = errors.map(e => e.character_name).join('、')
      error.value = `以下角色生成失败: ${names}`
    } else {
      error.value = ''
    }
  } catch (e) {
    console.error('Failed to generate all character images:', e)
    handleError(e.message)
  } finally {
    isGenerating.value = false
    for (const char of props.characters) {
      getCharacterData(char).loading = false
    }
  }
}

async function loadExistingImages() {
  if (!store.storyId) return

  try {
    const { character_images } = await getCharacterImages(store.storyId)
    if (character_images) {
      store.characterImages = character_images
      for (const char of props.characters) {
        const data = findCharacterImageEntry(character_images, char)
        if (data?.image_url) {
          getCharacterData(char).imageUrl = data.image_url
        }
      }
      return
    }
  } catch (e) {
    console.log('No existing character images')
  }

  if (store.characterImages && Object.keys(store.characterImages).length > 0) {
    for (const char of props.characters) {
      const data = findCharacterImageEntry(store.characterImages, char)
      if (data?.image_url) {
        getCharacterData(char).imageUrl = data.image_url
      }
    }
  }
}

// Reset local state when story changes
watch(() => store.storyId, (newId, oldId) => {
  if (newId !== oldId) {
    resetCharacterData()
    closePreview()
    loadExistingImages()
  }
})

watch(() => props.characters.map(char => `${char.id || ''}:${char.name}`), () => {
  resetCharacterData()
  closePreview()
  loadExistingImages()
})

onMounted(loadExistingImages)
onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<style scoped src="../style/components/characterdesign.css"></style>
