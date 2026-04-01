<template>
  <div class="export-panel">
    <button class="export-btn" @click="exportJSON">📥 导出 JSON</button>
    <button class="export-btn md" @click="exportMarkdown">📄 导出 Markdown</button>
  </div>
</template>

<script setup>
import { useStoryStore } from '../stores/story.js'

const store = useStoryStore()

function exportJSON() {
  const data = {
    meta: store.meta,
    input: store.input,
    characters: store.characters,
    relationships: store.relationships,
    outline: store.outline,
    scenes: store.scenes,
  }
  download(`${store.meta?.title || 'story'}.json`, JSON.stringify(data, null, 2), 'application/json')
}

function exportMarkdown() {
  const lines = []
  const m = store.meta
  const inp = store.input

  // 元数据头部
  lines.push(`# ${m?.title || '未命名剧本'}`)
  lines.push('')
  lines.push(`> **风格**：${inp?.genre || '-'}　**基调**：${inp?.tone || '-'}　**集数**：${m?.episodes || '-'}集`)
  lines.push(`> **主题**：${m?.theme || '-'}`)
  lines.push('')

  // 人物表
  if (store.characters.length) {
    lines.push('## 人物')
    for (const c of store.characters) {
      lines.push(`- **${c.name}**（${c.role}）：${c.description}`)
    }
    lines.push('')
  }

  // 人物关系
  if (store.relationships.length) {
    lines.push('## 人物关系')
    for (const r of store.relationships) {
      lines.push(`- ${r.source} → ${r.target}：${r.label}`)
    }
    lines.push('')
  }

  // 分集剧本
  lines.push('## 剧本')
  for (const ep of store.scenes) {
    lines.push('')
    lines.push(`### 第 ${ep.episode} 集　${ep.title}`)
    for (const scene of ep.scenes) {
      lines.push('')
      lines.push(`#### 场景 ${String(scene.scene_number).padStart(2, '0')}`)
      lines.push(`【环境】：${scene.environment}`)
      lines.push(`【画面】：${scene.visual}`)
      if (scene.audio?.length) {
        lines.push('【台词/旁白】：')
        for (const a of scene.audio) {
          lines.push(`（${a.character}）${a.line}`)
        }
      }
    }
  }

  download(`${m?.title || 'story'}.md`, lines.join('\n'), 'text/markdown')
}

function download(filename, content, type) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped src="../style/components/exportpanel.css"></style>
