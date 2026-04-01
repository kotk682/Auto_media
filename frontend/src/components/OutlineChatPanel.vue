<template>
  <!-- 遮罩 -->
  <div v-if="show" class="overlay" @click="$emit('close')" />

  <!-- 侧边面板 -->
  <div class="panel" :class="{ open: show }">
    <div class="panel-header">
      <span>AI 修改助手</span>
      <button class="close-btn" @click="$emit('close')">✕</button>
    </div>

    <div class="chat-history" ref="historyEl">
      <div v-if="messages.length === 0" class="empty-hint">
        告诉我你想怎么修改大纲，比如：<br>「把第3集改成主角失忆」
      </div>
      <div v-for="(msg, i) in messages" :key="i" :class="['bubble', msg.role]">
        <div class="bubble-text">{{ msg.text }}</div>
        <button
          v-if="msg.role === 'ai' && msg.refine"
          class="apply-btn"
          :disabled="msg.applied"
          @click="applyRefine(msg)"
        >
          {{ msg.applied ? '已应用 ✓' : '应用修改' }}
        </button>
      </div>
      <div v-if="streaming" class="bubble ai">
        <div class="bubble-text streaming">{{ streamingDisplayText }}<span class="cursor">|</span></div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        v-model="input"
        placeholder="描述你想修改的内容..."
        rows="3"
        @keydown.enter.exact.prevent="send"
      />
      <button class="send-btn" :disabled="!input.trim() || streaming" @click="send">
        {{ streaming ? '思考中...' : '发送' }}
      </button>
    </div>
    <div v-if="error" class="error-tip">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted, computed } from 'vue'
import { useStoryStore } from '../stores/story.js'
import { streamChat, refineStory } from '../api/story.js'
import { extractRefinePayload, stripRefineMarker } from '../utils/storyChat.js'

defineProps({ show: Boolean })
defineEmits(['close'])

const store = useStoryStore()
const messages = ref([])

let chatAbortController = null
onUnmounted(() => { chatAbortController?.abort() })
const input = ref('')
const streaming = ref(false)
const streamingText = ref('')
const error = ref('')
const historyEl = ref(null)
const streamingDisplayText = computed(() => stripRefineMarker(streamingText.value))

async function scrollToBottom() {
  await nextTick()
  if (historyEl.value) historyEl.value.scrollTop = historyEl.value.scrollHeight
}

watch(() => messages.value.length, scrollToBottom)
watch(streamingText, scrollToBottom)

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  input.value = ''
  error.value = ''

  messages.value = [...messages.value, { role: 'user', text }]

  streaming.value = true
  streamingText.value = ''

  chatAbortController?.abort()
  chatAbortController = new AbortController()

  await streamChat(
    store.storyId,
    {
      message: text,
      mode: 'outline',
      context: {
        meta: store.meta,
        characters: store.characters,
        outline: store.outline,
      },
    },
    (chunk) => { streamingText.value += chunk },
    () => {
      streaming.value = false
      const fullText = streamingText.value
      streamingText.value = ''
      const { displayText, refine } = extractRefinePayload(fullText)

      messages.value = [...messages.value, {
        role: 'ai',
        text: displayText,
        refine,
        applied: false,
      }]
    },
    (msg) => {
      streaming.value = false
      streamingText.value = ''
      error.value = msg || 'AI 响应失败，请重试'
    },
    chatAbortController.signal
  )
}

async function applyRefine(msg) {
  if (!msg.refine) return
  try {
    const res = await refineStory(store.storyId, msg.refine.change_type, msg.refine.change_summary)
    if (res) store.applyRefine(res)
    // 标记已应用（不可变更新）
    messages.value = messages.value.map(m =>
      m === msg ? { ...m, applied: true } : m
    )
  } catch {
    error.value = '应用失败，请重试'
  }
}
</script>

<style scoped src="../style/components/outlinechatpanel.css"></style>
