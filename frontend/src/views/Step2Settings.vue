<template>
  <div class="page">
    <StepIndicator :current="2" />
    <div class="content">
      <h1>完善故事设定</h1>
      <p class="subtitle">AI 已分析你的灵感，请选择或补充关键要素</p>

      <div class="idea-recap">
        <div><span class="recap-label">你的灵感：</span>{{ store.input.idea }}</div>
        <div class="tags-row">
          <span class="tag">{{ store.input.genre }}</span>
          <span class="tag">{{ store.input.tone }}</span>
        </div>
        <div v-if="store.analysis" class="analysis">
          <span class="recap-label">AI 分析：</span>{{ store.analysis }}
        </div>
        <div v-if="aiSummary" class="ai-summary">
          <span class="recap-label">AI 总结：</span>{{ aiSummary }}
        </div>
      </div>

      <!-- 动态追问选项组 -->
      <div v-for="group in store.suggestions" :key="group.label" class="suggestion-group">
        <div class="group-label">{{ group.label }}</div>
        <div class="opt-row">
          <button
            v-for="opt in group.options"
            :key="opt"
            class="opt-btn"
            :class="{ selected: selections[group.label] === opt }"
            @click="selectOption(group.label, opt)"
          >{{ opt }}</button>
        </div>
      </div>

      <!-- 自定义补充 -->
      <div class="custom-wrap">
        <div class="group-label">{{ store.placeholder || '或者直接告诉我你的想法...' }}</div>
        <textarea
          v-model="customText"
          placeholder="自由补充细节，发送后 AI 会帮你完善..."
          class="custom-input"
          rows="3"
        />
        <div class="custom-actions">
          <button class="clear-btn" @click="customText = ''" :disabled="!customText">清空</button>
          <button class="send-btn" @click="sendToAI" :disabled="!customText.trim() || chatLoading">
            {{ chatLoading ? '思考中...' : '✦ 发送给 AI' }}
          </button>
        </div>
        <div v-if="chatError" class="chat-error">{{ chatError }}</div>
      </div>

      <div class="btn-row">
        <button class="back-btn" @click="router.push('/step1')">← 返回</button>
        <button class="next-btn" :disabled="!composedSetting.trim() || loading" @click="submit">
          {{ loading ? '生成中...' : '生成大纲 →' }}
        </button>
      </div>
      <div v-if="error" class="error-tip">{{ error }}</div>
    </div>
  </div>
  <ApiKeyModal
    :show="showKeyModal"
    :type="keyModalType"
    :title="keyModalType === 'invalid' ? 'API Key 错误' : '未设置 API Key'"
    :message="keyModalMsg || '请先前往设置页填入 API Key，才能继续生成大纲。'"
    @close="showKeyModal = false"
  />
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import StepIndicator from '../components/StepIndicator.vue'
import ApiKeyModal from '../components/ApiKeyModal.vue'
import { useStoryStore } from '../stores/story.js'
import { useSettingsStore } from '../stores/settings.js'
import { generateOutline, streamChat } from '../api/story.js'

const router = useRouter()
const store = useStoryStore()
const settings = useSettingsStore()

const selections = ref({})
const customText = ref('')
const aiSummary = ref('')
const chatLoading = ref(false)
const chatError = ref('')
const loading = ref(false)
const error = ref('')
const showKeyModal = ref(false)
const keyModalType = ref('missing')
const keyModalMsg = ref('')

// 合成最终设定：选项 + 自定义文本 + AI总结
const composedSetting = computed(() => {
  const parts = []
  for (const [label, val] of Object.entries(selections.value)) {
    parts.push(`${label}：${val}`)
  }
  if (aiSummary.value) parts.push(`补充设定：${aiSummary.value}`)
  else if (customText.value.trim()) parts.push(`补充设定：${customText.value.trim()}`)
  return parts.join('；')
})

function selectOption(label, opt) {
  selections.value = { ...selections.value, [label]: opt }
}

function isAuthError(msg) {
  return /401|403|invalid|incorrect|unauthorized|api.?key/i.test(msg)
}

async function sendToAI() {
  if (!settings.useMock && !settings.apiKey) { chatError.value = '请先在设置页填入 API Key'; return }
  chatLoading.value = true
  chatError.value = ''
  const userMsg = customText.value
  customText.value = ''
  aiSummary.value = ''

  await streamChat(
    store.storyId,
    userMsg,
    (chunk) => { aiSummary.value += chunk },
    () => { chatLoading.value = false },
    (msg) => { chatLoading.value = false; chatError.value = msg || 'AI 响应失败，请重试' }
  )
}

async function submit() {
  if (!settings.useMock && !settings.apiKey) { showKeyModal.value = true; return }
  loading.value = true
  error.value = ''
  try {
    store.setSelectedSetting(composedSetting.value)
    const result = await generateOutline(store.storyId, composedSetting.value)
    store.setOutlineResult(result)
    store.setStep(3)
    router.push('/step3')
  } catch (e) {
    const msg = e.message || '请求失败'
    if (isAuthError(msg)) {
      keyModalType.value = 'invalid'
      keyModalMsg.value = 'API Key 无效或已过期，请检查后重新设置。'
      showKeyModal.value = true
    } else {
      error.value = msg
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { min-height: 100vh; background: #f5f5f7; padding: 32px 16px; }
.content { max-width: 600px; margin: 32px auto 0; }
h1 { font-size: 26px; font-weight: 700; margin-bottom: 6px; }
.subtitle { color: #888; margin-bottom: 24px; }
.idea-recap {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  font-size: 14px;
  color: #555;
  margin-bottom: 24px;
  border-left: 4px solid #6c63ff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.recap-label { font-weight: 600; color: #6c63ff; }
.tags-row { display: flex; gap: 6px; }
.tag {
  padding: 2px 10px;
  background: #f0eeff;
  color: #6c63ff;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}
.analysis { color: #666; line-height: 1.6; }
.ai-summary { padding-top: 8px; border-top: 1px solid #f0eeff; color: #444; line-height: 1.6; }
.suggestion-group { margin-bottom: 20px; }
.group-label { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 8px; }
.opt-row { display: flex; gap: 8px; flex-wrap: wrap; }
.opt-btn {
  padding: 8px 16px;
  border-radius: 20px;
  background: #fff;
  border: 2px solid #e0e0e0;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}
.opt-btn:hover { border-color: #6c63ff; color: #6c63ff; }
.opt-btn.selected {
  border-color: #6c63ff;
  background: #f0eeff;
  color: #6c63ff;
  font-weight: 600;
}
.custom-wrap { margin-top: 8px; margin-bottom: 8px; display: flex; flex-direction: column; gap: 8px; }
.custom-input {
  width: 100%;
  padding: 12px 16px;
  border-radius: 10px;
  border: 2px solid #e0e0e0;
  font-size: 14px;
  resize: none;
  line-height: 1.6;
  transition: border-color 0.2s;
  font-family: inherit;
}
.custom-input:focus { border-color: #6c63ff; outline: none; }
.custom-actions { display: flex; gap: 8px; justify-content: flex-end; }
.clear-btn {
  padding: 8px 16px;
  background: #fff;
  color: #888;
  border: 1.5px solid #e0e0e0;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}
.clear-btn:hover:not(:disabled) { border-color: #aaa; color: #555; }
.clear-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn {
  padding: 8px 18px;
  background: linear-gradient(135deg, #6c63ff, #a78bfa);
  color: #fff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.send-btn:hover:not(:disabled) { opacity: 0.9; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.chat-error { font-size: 12px; color: #e53935; }
.btn-row { display: flex; gap: 12px; margin-top: 28px; }
.back-btn {
  padding: 14px 20px;
  background: #fff;
  color: #555;
  border-radius: 12px;
  font-size: 15px;
  border: 2px solid #e0e0e0;
}
.next-btn {
  flex: 1;
  padding: 14px;
  background: #6c63ff;
  color: #fff;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
}
.next-btn:hover:not(:disabled) { background: #5a52e0; }
.next-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error-tip { margin-top: 12px; color: #e53935; font-size: 13px; text-align: center; }
</style>
