<template>
  <div class="page">
    <div class="header">
      <button class="back-btn" @click="router.back()">← 返回</button>
      <h1>API 设置</h1>
    </div>

    <div class="content">
      <!-- 当前模式提示 -->
      <div class="mode-banner" :class="store.useMock ? 'mock' : 'live'">
        <span class="mode-dot" />
        {{ store.useMock ? 'Mock 模式：使用预设数据，无需 API Key' : '真实模式：调用 LLM 接口，需要 API Key' }}
      </div>

      <div class="card">
        <div class="section-title">后端服务</div>
        <div class="field">
          <label>后端地址</label>
          <div class="input-row">
            <input v-model="backendUrl" placeholder="留空使用默认 http://localhost:8000" />
            <button class="test-btn" @click="testBackend" :disabled="testing">
              {{ backendStatus === 'ok' ? '✓' : backendStatus === 'fail' ? '✗' : testing ? '…' : '测试' }}
            </button>
          </div>
          <span class="hint">FastAPI 服务地址，留空走 Vite 代理</span>
          <span v-if="backendStatus === 'ok'" class="status-ok">连接正常</span>
          <span v-if="backendStatus === 'fail'" class="status-fail">{{ backendError }}</span>
        </div>

        <div class="divider" />

        <div class="section-title">LLM 配置</div>
        <div class="field">
          <label>服务商</label>
          <select v-model="provider" @change="onProviderChange" class="select-input">
            <option v-for="p in PROVIDERS" :key="p.id" :value="p.id">{{ p.label }}</option>
          </select>
        </div>
        <div class="field">
          <label>LLM Base URL</label>
          <input v-model="llmBaseUrl" placeholder="https://api.example.com/v1" />
          <span class="hint">选择服务商后自动填入，可手动修改</span>
        </div>
        <div class="field">
          <label>API Key</label>
          <div class="input-row">
            <input v-model="apiKey" :type="showKey ? 'text' : 'password'" placeholder="sk-..." />
            <button class="toggle-btn" @click="showKey = !showKey">{{ showKey ? '隐藏' : '显示' }}</button>
          </div>
          <span class="hint">密钥仅保存在本地浏览器中，不会上传服务器</span>
        </div>

        <div class="btn-row">
          <button class="clear-btn" @click="clearKey" :disabled="!apiKey">清除 Key</button>
          <button class="save-btn" @click="save">保存设置</button>
        </div>
        <div v-if="saved" class="saved-tip">已保存 ✓</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore, PROVIDERS } from '../stores/settings.js'

const router = useRouter()
const store = useSettingsStore()

const backendUrl = ref(store.backendUrl)
const provider = ref(store.provider)
const llmBaseUrl = ref(store.llmBaseUrl || PROVIDERS.find(p => p.id === store.provider)?.baseUrl || '')
const apiKey = ref(store.apiKey)
const saved = ref(false)
const showKey = ref(false)
const testing = ref(false)
const backendStatus = ref('')  // '' | 'ok' | 'fail'
const backendError = ref('')

function onProviderChange() {
  const p = PROVIDERS.find(p => p.id === provider.value)
  if (p && p.id !== 'custom') llmBaseUrl.value = p.baseUrl
}

async function testBackend() {
  testing.value = true
  backendStatus.value = ''
  backendError.value = ''
  try {
    const base = backendUrl.value ? backendUrl.value.replace(/\/$/, '') : ''
    const res = await fetch(`${base}/api/config`, { signal: AbortSignal.timeout(5000) })
    if (res.ok) {
      const data = await res.json()
      store.useMock = data.use_mock
      backendStatus.value = 'ok'
    } else {
      backendStatus.value = 'fail'
      backendError.value = `服务器返回 ${res.status}`
    }
  } catch (e) {
    backendStatus.value = 'fail'
    backendError.value = '无法连接，请检查后端是否启动'
  } finally {
    testing.value = false
  }
}

function clearKey() {
  apiKey.value = ''
}

function save() {
  store.save(backendUrl.value, provider.value, llmBaseUrl.value, apiKey.value)
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}
</script>

<style scoped>
.page { min-height: 100vh; background: #f5f5f7; padding: 32px 16px; }
.header { max-width: 600px; margin: 0 auto 16px; display: flex; align-items: center; gap: 16px; }
.back-btn {
  padding: 6px 14px; background: #fff; color: #6c63ff;
  border: 1.5px solid #6c63ff; border-radius: 8px;
  font-size: 13px; font-weight: 600; cursor: pointer;
}
.back-btn:hover { background: #f0eeff; }
h1 { font-size: 22px; font-weight: 700; margin: 0; }
.content { max-width: 600px; margin: 0 auto; }

.mode-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 10px;
  font-size: 13px; font-weight: 500; margin-bottom: 16px;
}
.mode-banner.mock { background: #fff8e1; color: #f59e0b; }
.mode-banner.live { background: #e8f5e9; color: #4caf50; }
.mode-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: currentColor;
}

.card { background: #fff; border-radius: 16px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.section-title { font-size: 12px; font-weight: 700; color: #a78bfa; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 16px; }
.divider { border: none; border-top: 1px solid #f0eeff; margin: 20px 0; }
.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
label { font-size: 13px; font-weight: 600; color: #444; }

.input-row { display: flex; gap: 8px; }
.input-row input { flex: 1; }

.select-input {
  padding: 10px 14px; border: 1.5px solid #e0e0e0; border-radius: 10px;
  font-size: 14px; background: #fff; outline: none; cursor: pointer; transition: border-color 0.2s;
}
.select-input:focus { border-color: #6c63ff; }
input {
  padding: 10px 14px; border: 1.5px solid #e0e0e0; border-radius: 10px;
  font-size: 14px; outline: none; transition: border-color 0.2s; width: 100%; box-sizing: border-box;
}
input:focus { border-color: #6c63ff; }
.hint { font-size: 12px; color: #aaa; }
.status-ok { font-size: 12px; color: #4caf50; font-weight: 600; }
.status-fail { font-size: 12px; color: #e53935; }

.test-btn, .toggle-btn {
  padding: 0 14px; border: 1.5px solid #e0e0e0; border-radius: 10px;
  font-size: 13px; background: #fff; color: #555; cursor: pointer;
  white-space: nowrap; transition: all 0.2s; flex-shrink: 0;
}
.test-btn:hover:not(:disabled), .toggle-btn:hover { border-color: #6c63ff; color: #6c63ff; }
.test-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-row { display: flex; gap: 10px; margin-top: 4px; }
.clear-btn {
  padding: 12px 20px; background: #fff; color: #888;
  border: 1.5px solid #e0e0e0; border-radius: 12px;
  font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.clear-btn:hover:not(:disabled) { border-color: #e53935; color: #e53935; }
.clear-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.save-btn {
  flex: 1; padding: 12px;
  background: linear-gradient(135deg, #6c63ff, #a78bfa);
  color: #fff; border-radius: 12px; font-size: 15px;
  font-weight: 600; transition: opacity 0.2s; cursor: pointer;
}
.save-btn:hover { opacity: 0.9; }
.saved-tip { text-align: center; margin-top: 12px; color: #4caf50; font-size: 14px; font-weight: 600; }
</style>
