<template>
  <div class="follow-up">
    <button
      v-for="opt in presetOptions"
      :key="opt.id"
      class="opt-btn"
      :class="{ selected: modelValue === opt.value }"
      @click="selectPreset(opt.value)"
    >
      {{ opt.label }}
    </button>

    <div class="custom-wrap">
      <textarea
        v-model="customText"
        placeholder="自定义设定，输入你的想法后点击发送，AI 会帮你完善..."
        class="custom-input"
        rows="3"
        @input="emit('update:modelValue', customText)"
        @focus="clearPreset"
      />
      <div class="custom-actions">
        <button class="clear-btn" @click="clearInput" :disabled="!customText">清空</button>
        <button class="send-btn" @click="sendToAI" :disabled="!customText.trim() || chatLoading">
          {{ chatLoading ? '思考中...' : '✦ 发送给 AI' }}
        </button>
      </div>
      <div v-if="chatError" class="chat-error">{{ chatError }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStoryStore } from '../stores/story.js'
import { useSettingsStore } from '../stores/settings.js'
import { streamChat } from '../api/story.js'

const props = defineProps({
  options: Array,
  modelValue: String,
})
const emit = defineEmits(['update:modelValue', 'update:aiSummary'])

const store = useStoryStore()
const settings = useSettingsStore()
const customText = ref('')
const chatLoading = ref(false)
const chatError = ref('')
const presetOptions = props.options.filter(o => o.id !== 'custom')

function selectPreset(val) {
  customText.value = ''
  emit('update:modelValue', val)
}

function clearPreset() {
  emit('update:modelValue', customText.value)
}

function clearInput() {
  customText.value = ''
  emit('update:modelValue', '')
}

async function sendToAI() {
  if (!settings.useMock && !settings.llmApiKey) { chatError.value = '请先在设置页填入 API Key'; return }
  chatLoading.value = true
  chatError.value = ''
  const userMsg = customText.value
  customText.value = ''
  emit('update:modelValue', '')

  await streamChat(
    store.storyId,
    userMsg,
    (chunk) => {
      customText.value += chunk
      emit('update:modelValue', customText.value)
    },
    () => {
        chatLoading.value = false
        emit('update:aiSummary', customText.value)
      },
    (msg) => { chatLoading.value = false; chatError.value = msg || 'AI 响应失败，请重试' }
  )
}
</script>

<style scoped>
.follow-up { display: flex; flex-direction: column; gap: 10px; }
.opt-btn {
  padding: 12px 16px;
  border-radius: 10px;
  background: #fff;
  border: 2px solid #e0e0e0;
  font-size: 14px;
  color: #333;
  text-align: left;
  transition: all 0.2s;
}
.opt-btn:hover { border-color: #6c63ff; }
.opt-btn.selected {
  border-color: #6c63ff;
  background: #f0eeff;
  color: #6c63ff;
  font-weight: 600;
}
.custom-wrap { display: flex; flex-direction: column; gap: 8px; }
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
  transition: all 0.2s;
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
</style>
