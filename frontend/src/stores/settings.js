import { defineStore } from 'pinia'

const PROVIDERS = [
  { id: 'claude', label: 'Anthropic Claude', baseUrl: 'https://api.anthropic.com' },
  { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { id: 'qwen', label: '阿里云 Qwen', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { id: 'zhipu', label: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4/' },
  { id: 'gemini', label: 'Google Gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1beta' },
  { id: 'custom', label: '自定义', baseUrl: '' },
]

export { PROVIDERS }

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    backendUrl: localStorage.getItem('backendUrl') || '',
    provider: localStorage.getItem('provider') || 'claude',
    llmBaseUrl: localStorage.getItem('llmBaseUrl') || '',
    apiKey: localStorage.getItem('apiKey') || '',
  }),
  getters: {
    useMock: (state) => !state.apiKey,
  },
  actions: {
    save(backendUrl, provider, llmBaseUrl, apiKey) {
      this.backendUrl = backendUrl
      this.provider = provider
      this.llmBaseUrl = llmBaseUrl
      this.apiKey = apiKey
      localStorage.setItem('backendUrl', backendUrl)
      localStorage.setItem('provider', provider)
      localStorage.setItem('llmBaseUrl', llmBaseUrl)
      localStorage.setItem('apiKey', apiKey)
    },
  },
})
