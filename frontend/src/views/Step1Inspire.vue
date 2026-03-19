<template>
  <div class="page">
    <StepIndicator :current="1" />
    <div class="content">
      <h1>输入你的灵感</h1>
      <p class="subtitle">一句话描述你的故事创意，越具体生成越准</p>

      <div class="inspire-box">
        <textarea
          v-model="idea"
          placeholder="例如：一个失忆的女孩在陌生城市遇到了一个神秘男人..."
          rows="4"
        />
        <div class="hint" :class="{ warn: idea.length > 0 && idea.length < 15 }">
          {{ idea.length < 15 && idea.length > 0 ? '再多说一点，比如主角名字或关键场景，效果更好' : `${idea.length} 字` }}
        </div>
        <button class="random-btn" @click="randomIdea">🎲 随机灵感</button>
      </div>

      <div class="section-label">风格类型</div>
      <div class="tag-group">
        <button
          v-for="g in GENRES"
          :key="g.value"
          class="tag-btn"
          :class="{ selected: genre === g.value }"
          @click="genre = g.value"
        >{{ g.icon }} {{ g.label }}</button>
      </div>

      <div class="section-label">故事基调</div>
      <div class="tag-group">
        <button
          v-for="t in TONES"
          :key="t.value"
          class="tag-btn"
          :class="{ selected: tone === t.value }"
          @click="tone = t.value"
        >{{ t.label }}</button>
      </div>

      <button class="next-btn" :disabled="!idea.trim() || !genre || !tone || loading" @click="submit">
        {{ loading ? '分析中...' : '下一步 →' }}
      </button>
      <div v-if="error" class="error-tip">{{ error }}</div>
    </div>
  </div>
  <ApiKeyModal
    :show="showKeyModal"
    :type="keyModalType"
    :title="keyModalType === 'invalid' ? 'API Key 错误' : '未设置 API Key'"
    :message="keyModalMsg || '请先前往设置页填入 API Key，才能开始使用。'"
    @close="showKeyModal = false"
  />
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import StepIndicator from '../components/StepIndicator.vue'
import ApiKeyModal from '../components/ApiKeyModal.vue'
import { useStoryStore } from '../stores/story.js'
import { useSettingsStore } from '../stores/settings.js'
import { analyzeIdea } from '../api/story.js'

const GENRES = [
  { value: '现代都市', label: '现代', icon: '🏙️' },
  { value: '古装', label: '古装', icon: '🏯' },
  { value: '悬疑', label: '悬疑', icon: '🔍' },
  { value: '甜宠', label: '甜宠', icon: '🍬' },
  { value: '赛博朋克', label: '赛博朋克', icon: '⚡' },
  { value: '无限流', label: '无限流', icon: '🌀' },
]

const TONES = [
  { value: '热血', label: '🔥 热血' },
  { value: '甜蜜', label: '🌸 甜蜜' },
  { value: '悬疑烧脑', label: '🧠 烧脑' },
  { value: '黑色幽默', label: '😈 黑色幽默' },
  { value: '治愈温情', label: '☀️ 治愈' },
]

const router = useRouter()
const store = useStoryStore()
const settings = useSettingsStore()

const idea = ref('')
const genre = ref('')
const tone = ref('')
const loading = ref(false)
const error = ref('')
const showKeyModal = ref(false)
const keyModalType = ref('missing')
const keyModalMsg = ref('')

function isAuthError(msg) {
  return /401|403|invalid|incorrect|unauthorized|api.?key/i.test(msg)
}

const RANDOM_IDEAS = [
  '一个失忆的女孩在陌生城市遇到了一个神秘男人，却发现他们曾经是恋人',
  '职场小白意外成为亿万富翁的私人助理，两人在朝夕相处中渐生情愫',
  '古代将军穿越到现代，遇到了长相与他亡妻一模一样的女孩',
  '赛博城市里的外卖小哥意外获得了时间静止的能力',
  '侦探在调查一起连环失踪案时，发现嫌疑人竟是自己的初恋',
]

function randomIdea() {
  idea.value = RANDOM_IDEAS[Math.floor(Math.random() * RANDOM_IDEAS.length)]
}

async function submit() {
  if (!settings.useMock && !settings.apiKey) { showKeyModal.value = true; return }
  loading.value = true
  error.value = ''
  try {
    store.setInput(idea.value, genre.value, tone.value)
    const result = await analyzeIdea(idea.value, genre.value, tone.value)
    store.setAnalyzeResult(result)
    store.setStep(2)
    router.push('/step2')
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
.inspire-box { position: relative; margin-bottom: 24px; }
textarea {
  width: 100%;
  padding: 16px;
  border-radius: 14px;
  border: 2px solid #e0e0e0;
  font-size: 15px;
  resize: none;
  background: #fff;
  transition: border-color 0.2s;
  line-height: 1.6;
  font-family: inherit;
}
textarea:focus { border-color: #6c63ff; outline: none; }
.hint {
  font-size: 12px;
  color: #aaa;
  text-align: right;
  margin-top: 4px;
}
.hint.warn { color: #f59e0b; }
.random-btn {
  margin-top: 8px;
  padding: 8px 16px;
  background: #f0eeff;
  color: #6c63ff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.2s;
}
.random-btn:hover { background: #e0d9ff; }
.section-label { font-size: 14px; font-weight: 600; color: #555; margin-bottom: 10px; margin-top: 20px; }
.tag-group { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.tag-btn {
  padding: 8px 16px;
  border-radius: 20px;
  background: #fff;
  border: 2px solid #e0e0e0;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}
.tag-btn:hover { border-color: #6c63ff; color: #6c63ff; }
.tag-btn.selected {
  border-color: #6c63ff;
  background: #f0eeff;
  color: #6c63ff;
  font-weight: 600;
}
.next-btn {
  margin-top: 32px;
  width: 100%;
  padding: 16px;
  background: #6c63ff;
  color: #fff;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 600;
  transition: background 0.2s;
}
.next-btn:hover:not(:disabled) { background: #5a52e0; }
.next-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error-tip { margin-top: 12px; color: #e53935; font-size: 13px; text-align: center; }
</style>
