<template>
  <div class="page">
    <div class="header">
      <button class="back-btn" @click="router.back()">← 返回</button>
      <h1>API 设置</h1>
    </div>

    <div class="content">
      <div class="mode-banner" :class="store.useMock ? 'mock' : 'live'">
        <span class="mode-dot" />
        {{ store.useMock ? 'Mock 模式：使用预设数据，无需 API Key' : '真实模式：调用 API 接口，可回退到后端 .env 默认值' }}
      </div>

      <!-- 后端服务 -->
      <div class="card card-backend">
        <div class="section-header">
          <span class="section-icon">⚙️</span>
          <span class="section-title">后端服务</span>
        </div>
        <div class="field">
          <label>后端地址</label>
          <div class="input-row">
            <input v-model="backendUrl" placeholder="留空时，本地开发走代理；部署后走当前站点同源地址" />
            <button class="test-btn" @click="testBackend" :disabled="testing">
              {{ backendStatus === 'ok' ? '✓' : backendStatus === 'fail' ? '✗' : testing ? '…' : '测试' }}
            </button>
          </div>
          <span class="hint">留空时，本地开发走 Vite 代理；部署后默认使用当前站点同源地址</span>
          <span v-if="backendStatus === 'ok'" class="status-ok">连接正常</span>
          <span v-if="backendStatus === 'fail'" class="status-fail">{{ backendError }}</span>
        </div>
      </div>

      <!-- 文本生成 -->
      <div class="card card-llm">
        <div class="section-header">
          <span class="section-icon">💬</span>
          <span class="section-title">文本生成（LLM）</span>
        </div>
        <div class="field">
          <label>服务商</label>
          <select v-model="llmProvider" @change="onLlmProviderChange" class="select-input">
            <option v-for="p in LLM_PROVIDERS" :key="p.id" :value="p.id">{{ p.label }}</option>
          </select>
        </div>
        <div class="field">
          <label>Base URL</label>
          <input v-model="llmBaseUrl" placeholder="https://api.example.com/v1" />
          <span class="hint">选择服务商后自动填入，可手动修改</span>
        </div>
        <div class="field">
          <label>API Key</label>
          <div class="input-row">
            <input v-model="llmApiKey" :type="showLlmKey ? 'text' : 'password'" placeholder="sk-..." />
            <button class="toggle-btn" @click="showLlmKey = !showLlmKey">{{ showLlmKey ? '隐藏' : '显示' }}</button>
          </div>
          <span class="hint">密钥仅保存在本地浏览器中</span>
          <span class="hint">留空时，后端会尝试使用 .env 中的默认 LLM 配置</span>
        </div>
        <div class="field">
          <label>模型</label>
          <select v-model="llmModelSelect" class="select-input">
            <option v-for="m in currentLlmModels" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <input
            v-if="llmModelSelect === 'custom'"
            v-model="llmModelCustom"
            placeholder="输入模型名称，如 claude-3-5-sonnet-latest"
            class="model-custom-input"
          />
        </div>

        <!-- 高级选项 -->
        <div class="advanced-toggle" @click="showAdvanced = !showAdvanced">
          <span class="advanced-arrow" :class="{ open: showAdvanced }">▶</span>
          高级选项
        </div>
        <div v-if="showAdvanced" class="advanced-section">
          <div class="adv-row">
            <span id="use-script-model-label" class="adv-label">分镜专用配置</span>
            <label class="toggle-switch">
              <input type="checkbox" v-model="useScriptModel" @change="onScriptModelToggle" aria-labelledby="use-script-model-label" />
              <span class="toggle-track" />
            </label>
          </div>
          <span class="hint">启用后，分镜生成步骤将使用下方独立配置（服务商 / API Key / 模型），其余步骤仍使用上方默认 LLM 配置。</span>
          <template v-if="useScriptModel">
            <div class="field field-top-gap field-compact">
              <label for="script-provider">服务商</label>
              <select id="script-provider" v-model="scriptProvider" @change="onScriptProviderChange" class="select-input">
                <option v-for="p in LLM_PROVIDERS" :key="p.id" :value="p.id">{{ p.label }}</option>
              </select>
            </div>
            <div class="field field-compact">
              <label for="script-base-url">Base URL</label>
              <input id="script-base-url" v-model="scriptBaseUrl" placeholder="https://api.example.com/v1" />
            </div>
            <div class="field field-compact">
              <label for="script-api-key">API Key</label>
              <div class="input-row">
                <input id="script-api-key" v-model="scriptApiKey" :type="showScriptKey ? 'text' : 'password'" placeholder="sk-..." />
                <button class="toggle-btn" @click="showScriptKey = !showScriptKey">{{ showScriptKey ? '隐藏' : '显示' }}</button>
              </div>
              <span class="hint">密钥仅保存在本地浏览器中</span>
            </div>
            <div class="field field-compact">
              <label for="script-model-select">模型</label>
              <select id="script-model-select" v-model="scriptModelSelect" class="select-input">
                <option v-for="m in currentScriptModels" :key="m.id" :value="m.id">{{ m.label }}</option>
              </select>
              <input
                v-if="scriptModelSelect === 'custom'"
                id="script-model-custom"
                v-model="scriptModelCustom"
                aria-label="自定义模型名称"
                placeholder="输入模型名称，如 claude-opus-4-6"
                class="model-custom-input"
              />
            </div>
          </template>
        </div>
      </div>

      <!-- 图片生成 -->
      <div class="card card-image">
        <div class="section-header">
          <span class="section-icon">🖼️</span>
          <span class="section-title">图片生成</span>
        </div>
        <div class="field">
          <label>服务商</label>
          <select v-model="imageProvider" @change="onImageProviderChange" class="select-input">
            <option v-for="p in IMAGE_PROVIDERS" :key="p.id" :value="p.id">{{ p.label }}</option>
          </select>
        </div>
        <div class="field">
          <label>Base URL</label>
          <input v-model="imageBaseUrl" placeholder="https://api.siliconflow.cn/v1" />
          <span class="hint">兼容 OpenAI /images/generations 接口的服务均可使用</span>
        </div>
        <div class="field">
          <label>API Key</label>
          <div class="input-row">
            <input v-model="imageApiKey" :type="showImageKey ? 'text' : 'password'" placeholder="sk-..." />
            <button class="toggle-btn" @click="showImageKey = !showImageKey">{{ showImageKey ? '隐藏' : '显示' }}</button>
          </div>
          <span class="hint">密钥仅保存在本地浏览器中</span>
        </div>
        <div class="field">
          <label>模型</label>
          <select v-if="!(currentImageModels.length === 1 && currentImageModels[0].id === 'custom')" v-model="imageModelSelect" class="select-input">
            <option v-for="m in currentImageModels" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <input
            v-if="imageModelSelect === 'custom'"
            v-model="imageModelCustom"
            :placeholder="imageProvider === 'doubao' ? '输入端点 ID，如 ep-xxxxxxxx' : '输入模型名称，如 black-forest-labs/FLUX.1-schnell'"
            class="model-custom-input"
          />
        </div>
      </div>

      <!-- 视频生成 -->
      <div class="card card-video">
        <div class="section-header">
          <span class="section-icon">🎬</span>
          <span class="section-title">视频生成</span>
        </div>
        <div class="field">
          <label>服务商</label>
          <select v-model="videoProvider" @change="onVideoProviderChange" class="select-input">
            <option v-for="p in VIDEO_PROVIDERS" :key="p.id" :value="p.id">{{ p.label }}</option>
          </select>
        </div>
        <div class="field">
          <label>Base URL</label>
          <input v-model="videoBaseUrl" placeholder="https://dashscope.aliyuncs.com/api/v1" />
          <span class="hint">{{ videoProvider === 'kling' ? 'Kling 图生视频接口地址' : 'DashScope 图生视频接口地址' }}</span>
        </div>
        <div class="field">
          <label>API Key</label>
          <div class="input-row">
            <input v-model="videoApiKey" :type="showVideoKey ? 'text' : 'password'" :placeholder="videoProvider === 'kling' ? 'access_key_id:secret_key' : 'sk-...'" />
            <button class="toggle-btn" @click="showVideoKey = !showVideoKey">{{ showVideoKey ? '隐藏' : '显示' }}</button>
          </div>
          <span v-if="videoProvider === 'kling'" class="hint">Kling 格式：access_key_id:secret_key（冒号连接两个字段）</span>
          <span v-else-if="videoProvider === 'minimax'" class="hint">MiniMax 开放平台获取 API Key，填入后直接使用</span>
          <span v-else class="hint">密钥仅保存在本地浏览器中</span>
        </div>
        <div class="field">
          <label>模型</label>
          <select v-if="!(currentVideoModels.length === 1 && currentVideoModels[0].id === 'custom')" v-model="videoModelSelect" class="select-input">
            <option v-for="m in currentVideoModels" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <input
            v-if="videoModelSelect === 'custom'"
            v-model="videoModelCustom"
            :placeholder="videoProvider === 'doubao' ? '输入端点 ID，如 ep-xxxxxxxx' : '输入模型名称，如 wan2.1-i2v-turbo'"
            class="model-custom-input"
          />
        </div>
      </div>

      <div class="btn-row">
        <button class="save-btn" @click="save">保存设置</button>
      </div>
      <div v-if="saved" class="saved-tip">已保存 ✓</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore, LLM_PROVIDERS, IMAGE_PROVIDERS, VIDEO_PROVIDERS } from '../stores/settings.js'
import { resolveBackendHealthUrl } from '../utils/backend.js'

const router = useRouter()
const store = useSettingsStore()

// 后端
const backendUrl    = ref(store.backendUrl)
const testing       = ref(false)
const backendStatus = ref('')
const backendError  = ref('')

// LLM
const llmProvider = ref(store.llmProvider || 'claude')
const llmBaseUrl  = ref(store.llmBaseUrl  || LLM_PROVIDERS.find(p => p.id === (store.llmProvider || 'claude'))?.baseUrl || '')
const llmApiKey   = ref(store.llmApiKey)
const showLlmKey  = ref(false)

const currentLlmModels = computed(() =>
  LLM_PROVIDERS.find(p => p.id === llmProvider.value)?.models ?? [{ id: 'custom', label: '自定义...' }]
)
const _initLlmModel = () => {
  const stored = store.llmModel
  const isPreset = !!stored && currentLlmModels.value.some(m => m.id !== 'custom' && m.id === stored)
  return { select: isPreset ? stored : (stored ? 'custom' : currentLlmModels.value[0]?.id ?? 'custom'), custom: isPreset ? '' : (stored || '') }
}
const { select: _ls, custom: _lc } = _initLlmModel()
const llmModelSelect = ref(_ls)
const llmModelCustom = ref(_lc)

// 高级选项：脚本生成专用配置
const _hasScript = !!(store.scriptModel || store.scriptApiKey || store.scriptBaseUrl || store.scriptProvider)
const showAdvanced   = ref(_hasScript)
const useScriptModel = ref(_hasScript)
const scriptProvider = ref(store.scriptProvider || store.llmProvider || 'claude')
const scriptBaseUrl  = ref(store.scriptBaseUrl  || LLM_PROVIDERS.find(p => p.id === (store.scriptProvider || store.llmProvider || 'claude'))?.baseUrl || '')
const scriptApiKey   = ref(store.scriptApiKey)
const showScriptKey  = ref(false)

const currentScriptModels = computed(() =>
  LLM_PROVIDERS.find(p => p.id === scriptProvider.value)?.models ?? [{ id: 'custom', label: '自定义...' }]
)
const _initScriptModel = () => {
  const stored = store.scriptModel
  const isPreset = !!stored && currentScriptModels.value.some(m => m.id !== 'custom' && m.id === stored)
  return { select: isPreset ? stored : (stored ? 'custom' : currentScriptModels.value[0]?.id ?? 'custom'), custom: isPreset ? '' : (stored || '') }
}
const { select: _ss, custom: _sc } = _initScriptModel()
const scriptModelSelect = ref(_ss)
const scriptModelCustom = ref(_sc)

function onScriptProviderChange() {
  const p = LLM_PROVIDERS.find(prov => prov.id === scriptProvider.value)
  if (p && p.id !== 'custom') scriptBaseUrl.value = p.baseUrl
  scriptModelSelect.value = currentScriptModels.value[0]?.id ?? 'custom'
  scriptModelCustom.value = ''
}

function onScriptModelToggle() {
  scriptProvider.value    = llmProvider.value
  scriptBaseUrl.value     = llmBaseUrl.value
  scriptApiKey.value      = ''
  scriptModelSelect.value = llmModelSelect.value
  scriptModelCustom.value = llmModelCustom.value
}

// Image
const imageProvider = ref(store.imageProvider || 'siliconflow')
const imageBaseUrl  = ref(store.imageBaseUrl  || IMAGE_PROVIDERS.find(p => p.id === (store.imageProvider || 'siliconflow'))?.baseUrl || '')
const imageApiKey   = ref(store.imageApiKey)
const showImageKey  = ref(false)

const currentImageModels = computed(() =>
  IMAGE_PROVIDERS.find(p => p.id === imageProvider.value)?.models ?? [{ id: 'custom', label: '自定义...' }]
)
const _initImageModel = () => {
  const stored = store.imageModel
  const isPreset = !!stored && currentImageModels.value.some(m => m.id !== 'custom' && m.id === stored)
  return { select: isPreset ? stored : (stored ? 'custom' : currentImageModels.value[0]?.id ?? 'custom'), custom: isPreset ? '' : (stored || '') }
}
const { select: _is, custom: _ic } = _initImageModel()
const imageModelSelect = ref(_is)
const imageModelCustom = ref(_ic)

// Video
const videoProvider = ref(store.videoProvider || 'dashscope')
const videoBaseUrl  = ref(store.videoBaseUrl  || VIDEO_PROVIDERS.find(p => p.id === (store.videoProvider || 'dashscope'))?.baseUrl || '')
const videoApiKey   = ref(store.videoApiKey)
const showVideoKey  = ref(false)

const currentVideoModels = computed(() =>
  VIDEO_PROVIDERS.find(p => p.id === videoProvider.value)?.models ?? [{ id: 'custom', label: '自定义...' }]
)
const _initVideoModel = () => {
  const stored = store.videoModel
  const isPreset = !!stored && currentVideoModels.value.some(m => m.id !== 'custom' && m.id === stored)
  return { select: isPreset ? stored : (stored ? 'custom' : currentVideoModels.value[0]?.id ?? 'custom'), custom: isPreset ? '' : (stored || '') }
}
const { select: _vs, custom: _vc } = _initVideoModel()
const videoModelSelect = ref(_vs)
const videoModelCustom = ref(_vc)

const saved = ref(false)

function onLlmProviderChange() {
  const p = LLM_PROVIDERS.find(p => p.id === llmProvider.value)
  if (p && p.id !== 'custom') llmBaseUrl.value = p.baseUrl
  llmModelSelect.value = currentLlmModels.value[0]?.id ?? 'custom'
  llmModelCustom.value = ''
}

function onImageProviderChange() {
  const p = IMAGE_PROVIDERS.find(p => p.id === imageProvider.value)
  if (p && p.id !== 'custom') imageBaseUrl.value = p.baseUrl
  imageModelSelect.value = currentImageModels.value[0]?.id ?? 'custom'
  imageModelCustom.value = ''
}

function onVideoProviderChange() {
  const p = VIDEO_PROVIDERS.find(p => p.id === videoProvider.value)
  if (p && p.id !== 'custom') videoBaseUrl.value = p.baseUrl
  videoModelSelect.value = currentVideoModels.value[0]?.id ?? 'custom'
  videoModelCustom.value = ''
}

async function testBackend() {
  testing.value = true
  backendStatus.value = ''
  backendError.value = ''
  try {
    const res = await fetch(resolveBackendHealthUrl(backendUrl.value), { signal: AbortSignal.timeout(5000) })
    backendStatus.value = res.ok ? 'ok' : 'fail'
    if (!res.ok) backendError.value = `服务器返回 ${res.status}`
  } catch {
    backendStatus.value = 'fail'
    backendError.value = '无法连接，请检查后端是否启动'
  } finally {
    testing.value = false
  }
}

const getModel = (select, custom) => select === 'custom' ? custom : select

function save() {
  const scriptModelValue = useScriptModel.value
    ? getModel(scriptModelSelect.value, scriptModelCustom.value)
    : ''
  store.save({
    backendUrl:     backendUrl.value,
    llmProvider:    llmProvider.value,
    llmApiKey:      llmApiKey.value,
    llmBaseUrl:     llmBaseUrl.value,
    llmModel:       getModel(llmModelSelect.value, llmModelCustom.value),
    scriptModel:    scriptModelValue,
    scriptProvider: useScriptModel.value ? scriptProvider.value : '',
    scriptApiKey:   useScriptModel.value ? scriptApiKey.value   : '',
    scriptBaseUrl:  useScriptModel.value ? scriptBaseUrl.value  : '',
    imageProvider:  imageProvider.value,
    imageApiKey:    imageApiKey.value,
    imageBaseUrl:   imageBaseUrl.value,
    imageModel:     getModel(imageModelSelect.value, imageModelCustom.value),
    videoProvider:  videoProvider.value,
    videoApiKey:    videoApiKey.value,
    videoBaseUrl:   videoBaseUrl.value,
    videoModel:     getModel(videoModelSelect.value, videoModelCustom.value),
  })
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}
</script>

<style scoped src="../style/settingsview.css"></style>
