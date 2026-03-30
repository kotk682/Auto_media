import { defineStore } from 'pinia'

// Mock 改为显式开启：只有设置 VITE_ENABLE_MOCK=true 时才启用。
// 这样浏览器本地未填写 llmApiKey 时，前端不会抢先进入 Mock，后端仍可使用 .env 默认凭证。
const MOCK_ENABLED = import.meta.env.VITE_ENABLE_MOCK === 'true'

function shouldSendLlmProvider(state) {
  const provider = String(state.llmProvider || '').trim()
  if (!provider) return false

  // 默认 claude 只是前端展示默认值；当用户未填写任何本地 LLM 配置时，不要把它发给后端，
  // 否则会覆盖后端 .env 里的 DEFAULT_LLM_PROVIDER。
  return (
    provider !== 'claude'
    || !!String(state.llmApiKey || '').trim()
    || !!String(state.llmModel || '').trim()
  )
}

function hasStoredSetting(key) {
  if (typeof window === 'undefined' || !window.localStorage) return false
  return window.localStorage.getItem(key) !== null
}

function shouldSendImageConfig(state) {
  return (
    hasStoredSetting('imageProvider')
    || hasStoredSetting('imageApiKey')
    || hasStoredSetting('imageBaseUrl')
    || hasStoredSetting('imageModel')
    || !!String(state.imageApiKey || '').trim()
    || !!String(state.imageBaseUrl || '').trim()
    || !!String(state.imageModel || '').trim()
  )
}

function shouldSendVideoConfig(state) {
  return (
    hasStoredSetting('videoProvider')
    || hasStoredSetting('videoApiKey')
    || hasStoredSetting('videoBaseUrl')
    || hasStoredSetting('videoModel')
    || !!String(state.videoApiKey || '').trim()
    || !!String(state.videoBaseUrl || '').trim()
    || !!String(state.videoModel || '').trim()
  )
}

export const LLM_PROVIDERS = [
  {
    id: 'claude', label: 'Anthropic Claude',
    baseUrl: 'https://api.anthropic.com',
    models: [
      { id: 'claude-opus-4-6',           label: 'Claude Opus 4.6' },
      { id: 'claude-sonnet-4-6',         label: 'Claude Sonnet 4.6' },
      { id: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
      { id: 'claude-3-5-sonnet-latest',  label: 'Claude 3.5 Sonnet' },
      { id: 'claude-3-5-haiku-latest',   label: 'Claude 3.5 Haiku' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'openai', label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    models: [
      { id: 'gpt-4o',      label: 'GPT-4o' },
      { id: 'gpt-4o-mini', label: 'GPT-4o mini' },
      { id: 'o1',          label: 'o1' },
      { id: 'o1-mini',     label: 'o1-mini' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'siliconflow', label: 'SiliconFlow',
    baseUrl: 'https://api.siliconflow.cn/v1',
    models: [
      { id: 'deepseek-ai/DeepSeek-V3',   label: 'DeepSeek V3' },
      { id: 'deepseek-ai/DeepSeek-R1',   label: 'DeepSeek R1' },
      { id: 'Qwen/Qwen2.5-72B-Instruct', label: 'Qwen2.5 72B' },
      { id: 'Qwen/Qwen2.5-7B-Instruct',  label: 'Qwen2.5 7B' },
      { id: 'THUDM/glm-4-9b-chat',       label: 'GLM-4 9B' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'qwen', label: '阿里云 Qwen',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: [
      { id: 'qwen-max',   label: 'Qwen Max' },
      { id: 'qwen-plus',  label: 'Qwen Plus' },
      { id: 'qwen-turbo', label: 'Qwen Turbo' },
      { id: 'qwen-long',  label: 'Qwen Long' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'zhipu', label: '智谱 GLM',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4/',
    models: [
      { id: 'glm-4-plus',  label: 'GLM-4 Plus' },
      { id: 'glm-4-air',   label: 'GLM-4 Air' },
      { id: 'glm-4-flash', label: 'GLM-4 Flash' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'gemini', label: 'Google Gemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    models: [
      { id: 'gemini-2.0-flash',      label: 'Gemini 2.0 Flash' },
      { id: 'gemini-2.0-flash-lite', label: 'Gemini 2.0 Flash Lite' },
      { id: 'gemini-1.5-pro',        label: 'Gemini 1.5 Pro' },
      { id: 'gemini-1.5-flash',      label: 'Gemini 1.5 Flash' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'custom', label: '自定义',
    baseUrl: '',
    models: [{ id: 'custom', label: '自定义...' }],
  },
]

export const IMAGE_PROVIDERS = [
  {
    id: 'siliconflow', label: 'SiliconFlow',
    baseUrl: 'https://api.siliconflow.cn/v1',
    models: [
      { id: 'black-forest-labs/FLUX.1-schnell',             label: 'FLUX.1 Schnell（免费·快）' },
      { id: 'black-forest-labs/FLUX.1-dev',                 label: 'FLUX.1 Dev' },
      { id: 'black-forest-labs/FLUX.1-pro',                 label: 'FLUX.1 Pro（旗舰）' },
      { id: 'Pro/black-forest-labs/FLUX.1-schnell',         label: 'FLUX.1 Schnell Pro' },
      { id: 'Pro/black-forest-labs/FLUX.1-dev',             label: 'FLUX.1 Dev Pro' },
      { id: 'stabilityai/stable-diffusion-3-5-large',       label: 'SD 3.5 Large' },
      { id: 'stabilityai/stable-diffusion-3-5-large-turbo', label: 'SD 3.5 Large Turbo' },
      { id: 'stabilityai/stable-diffusion-3-medium',        label: 'SD 3 Medium' },
      { id: 'Kwai-Kolors/Kolors',                           label: 'Kolors' },
      { id: 'HiDream-ai/HiDream-I1-Full',                   label: 'HiDream I1 Full' },
      { id: 'HiDream-ai/HiDream-I1-Dev',                    label: 'HiDream I1 Dev' },
      { id: 'Ideogram-AI/Ideogram-V2',                      label: 'Ideogram V2' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'doubao', label: '豆包 (火山方舟)',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    models: [
      { id: 'custom', label: '填写端点 ID（ep-xxx）' },
    ],
  },
  {
    id: 'custom', label: '自定义',
    baseUrl: '',
    models: [{ id: 'custom', label: '自定义...' }],
  },
]

export const VIDEO_PROVIDERS = [
  {
    id: 'dashscope', label: '阿里云 DashScope',
    baseUrl: 'https://dashscope.aliyuncs.com/api/v1',
    models: [
      { id: 'wan2.6-i2v-plus',  label: 'Wan2.6 I2V Plus（质量高）' },
      { id: 'wan2.6-i2v-flash', label: 'Wan2.6 I2V Flash（快）' },
      { id: 'wan2.1-i2v-plus',  label: 'Wan2.1 I2V Plus' },
      { id: 'wan2.1-i2v-turbo', label: 'Wan2.1 I2V Turbo' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'kling', label: '快手可灵 Kling',
    baseUrl: 'https://api.klingai.com',
    models: [
      { id: 'kling-v2-master',   label: 'Kling v2 Master（最强）' },
      { id: 'kling-v1-5-pro',    label: 'Kling v1.5 Pro' },
      { id: 'kling-v1-pro',      label: 'Kling v1 Pro' },
      { id: 'kling-v1-standard', label: 'Kling v1 Standard' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'minimax', label: 'MiniMax 海螺视频 (Hailuo)',
    baseUrl: 'https://api.minimaxi.chat',
    models: [
      { id: 'video-01',      label: 'Video-01（主力，I2V）' },
      { id: 'video-01-live', label: 'Video-01 Live（动态感强）' },
      { id: 'custom', label: '自定义...' },
    ],
  },
  {
    id: 'doubao', label: '豆包 Seedance (火山方舟)',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    models: [
      { id: 'doubao-seedance-1-5-pro-251215', label: 'Seedance 1.5 Pro' },
      { id: 'doubao-seedance-1-0-lite-250528', label: 'Seedance 1.0 Lite（快）' },
      { id: 'custom', label: '填写端点 ID（ep-xxx）' },
    ],
  },
  {
    id: 'custom', label: '自定义',
    baseUrl: '',
    models: [{ id: 'custom', label: '自定义...' }],
  },
]

function migrateV1() {
  const oldKey = localStorage.getItem('apiKey')
  if (oldKey && !localStorage.getItem('llmApiKey')) {
    localStorage.setItem('llmApiKey', oldKey)
    localStorage.setItem('llmProvider', localStorage.getItem('provider') || 'claude')
    ;['apiKey', 'provider', 'textEnabled', 'textProvider', 'textApiKey', 'textBaseUrl', 'textModel',
      'imageEnabled', 'videoEnabled'].forEach(k => localStorage.removeItem(k))
  }
}
migrateV1()

const ls = (key, fallback = '') => localStorage.getItem(key) ?? fallback

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    backendUrl:    ls('backendUrl'),
    llmProvider:   ls('llmProvider', 'claude'),
    llmApiKey:     ls('llmApiKey'),
    llmBaseUrl:    ls('llmBaseUrl'),
    llmModel:      ls('llmModel'),
    scriptModel:    ls('scriptModel'),
    scriptProvider: ls('scriptProvider'),
    scriptApiKey:   ls('scriptApiKey'),
    scriptBaseUrl:  ls('scriptBaseUrl'),
    imageProvider: ls('imageProvider', 'siliconflow'),
    imageApiKey:   ls('imageApiKey'),
    imageBaseUrl:  ls('imageBaseUrl'),
    imageModel:    ls('imageModel'),
    videoProvider: ls('videoProvider', 'dashscope'),
    videoApiKey:   ls('videoApiKey'),
    videoBaseUrl:  ls('videoBaseUrl'),
    videoModel:    ls('videoModel'),
  }),

  getters: {
    useMock: (state) => MOCK_ENABLED && !String(state.llmApiKey || '').trim(),

    // 未显式保存任何前端 LLM 设置时，不发送默认 claude，交给后端 .env 决定默认 provider。
    effectiveLlmProvider:  (state) => shouldSendLlmProvider(state) ? state.llmProvider : '',
    // 本地未填写 LLM key 时，不发送 base_url，避免把默认官方地址误判成“自定义中转”。
    effectiveLlmBaseUrl:   (state) => String(state.llmApiKey || '').trim() ? state.llmBaseUrl : '',
    effectiveLlmApiKey:    (state) => state.llmApiKey,
    effectiveLlmModel:     (state) => state.llmModel,
    effectiveScriptModel:   (state) => state.scriptModel,
    effectiveScriptProvider:(state) => state.scriptProvider,
    effectiveScriptApiKey:  (state) => state.scriptApiKey,
    effectiveScriptBaseUrl: (state) => String(state.scriptApiKey || '').trim() ? state.scriptBaseUrl : '',

    effectiveImageProvider: (state) => shouldSendImageConfig(state) ? state.imageProvider : '',
    effectiveImageApiKey:   (state) => shouldSendImageConfig(state) ? state.imageApiKey : '',
    effectiveImageBaseUrl:  (state) => shouldSendImageConfig(state) ? state.imageBaseUrl : '',
    effectiveImageModel:    (state) => shouldSendImageConfig(state) ? state.imageModel : '',

    effectiveVideoProvider: (state) => shouldSendVideoConfig(state) ? state.videoProvider : '',
    effectiveVideoApiKey:   (state) => shouldSendVideoConfig(state) ? state.videoApiKey : '',
    effectiveVideoBaseUrl:  (state) => shouldSendVideoConfig(state) ? state.videoBaseUrl : '',
    effectiveVideoModel:    (state) => shouldSendVideoConfig(state) ? state.videoModel : '',
  },

  actions: {
    save(data) {
      const KEYS = [
        'backendUrl',
        'llmProvider', 'llmApiKey', 'llmBaseUrl', 'llmModel',
        'scriptModel', 'scriptProvider', 'scriptApiKey', 'scriptBaseUrl',
        'imageProvider', 'imageApiKey', 'imageBaseUrl', 'imageModel',
        'videoProvider', 'videoApiKey', 'videoBaseUrl', 'videoModel',
      ]
      for (const key of KEYS) {
        if (key in data) {
          this[key] = data[key]
          localStorage.setItem(key, String(data[key]))
        }
      }
    },
  },
})
