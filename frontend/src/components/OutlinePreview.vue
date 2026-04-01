<template>
  <div class="outline-preview">
    <div class="meta-card">
      <h2>{{ meta.title }}</h2>
      <div class="meta-tags">
        <span class="tag">{{ meta.genre }}</span>
        <span class="tag">共 {{ meta.episodes }} 集</span>
      </div>
      <p class="theme">{{ meta.theme }}</p>
    </div>

    <div class="section">
      <div class="section-header">
        <h3>主要角色 <span class="hint-text">双击可编辑</span></h3>
      </div>
      <div class="characters">
        <div
          v-for="c in characters"
          :key="c.id || c.name"
          class="char-card"
          :class="{ editing: editingChar === (c.id || c.name) }"
        >
          <div class="char-header">
            <div class="char-main" @dblclick="startEditChar(c)">
              <template v-if="editingChar === (c.id || c.name)">
                <div class="char-edit-row">
                  <span class="char-name-static">{{ c.name }}</span>
                  <span class="char-role">{{ c.role }}</span>
                </div>
                <textarea v-model="editCharDesc" class="edit-char-desc" rows="2" @keydown.esc="cancelEditChar" />
                <div class="edit-actions">
                  <button class="save-btn" @click="saveEditChar(c)">保存</button>
                  <button class="cancel-btn" @click="cancelEditChar">取消</button>
                </div>
              </template>
              <template v-else>
                <div class="char-name">{{ c.name }} <span class="char-role">{{ c.role }}</span></div>
                <div class="char-desc">{{ c.description }}</div>
              </template>
            </div>
            <button class="ai-icon-btn" @click="openCharacterChat(c)" title="AI 修改此角色">✦</button>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <h3>剧情大纲 <span class="hint-text">双击可编辑</span></h3>
      <div class="outline-list">
        <div
          v-for="ep in outline"
          :key="ep.episode"
          class="ep-item"
          :class="{ editing: editingEp === ep.episode }"
        >
          <div class="ep-left">
            <div class="ep-num">第 {{ ep.episode }} 集</div>
          </div>
          <div class="ep-content" @dblclick="startEdit(ep)">
            <template v-if="editingEp === ep.episode">
              <input v-model="editTitle" class="edit-title" @keydown.enter="saveEdit" @keydown.esc="cancelEdit" />
              <textarea v-model="editSummary" class="edit-summary" rows="3" @keydown.esc="cancelEdit" />
              <div class="edit-actions">
                <button class="save-btn" @click="saveEdit">保存</button>
                <button class="cancel-btn" @click="cancelEdit">取消</button>
              </div>
            </template>
            <template v-else>
              <div class="ep-title">{{ ep.title }}</div>
              <div class="ep-summary">{{ ep.summary }}</div>
            </template>
          </div>
          <button class="ai-icon-btn" @click="openEpisodeChat(ep)" title="AI 修改此集">✦</button>
        </div>
      </div>
    </div>

    <CharacterChatPanel
      :show="characterChatOpen"
      :character="selectedCharacter"
      @close="characterChatOpen = false"
    />
    <EpisodeChatPanel
      :show="episodeChatOpen"
      :episode="selectedEpisode"
      @close="episodeChatOpen = false"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStoryStore } from '../stores/story.js'
import { patchStory, refineStory } from '../api/story.js'
import CharacterChatPanel from './CharacterChatPanel.vue'
import EpisodeChatPanel from './EpisodeChatPanel.vue'
import { findCharacterByRef, getCharacterKey } from '../utils/character.js'

defineProps({ meta: Object, characters: Array, outline: Array })

const store = useStoryStore()
const editingEp = ref(null)
const editTitle = ref('')
const editSummary = ref('')
const editingChar = ref(null)
const editCharDesc = ref('')
const characterChatOpen = ref(false)
const selectedCharacter = ref(null)
const episodeChatOpen = ref(false)
const selectedEpisode = ref(null)

function startEdit(ep) {
  editingEp.value = ep.episode
  editTitle.value = ep.title
  editSummary.value = ep.summary
}

async function saveEdit() {
  const ep = store.outline.find(e => e.episode === editingEp.value)
  if (!ep) return
  const oldSummary = ep ? ep.summary : ''
  const epNum = editingEp.value
  const nextOutline = store.outline.map(item => (
    item.episode === epNum
      ? { ...item, title: editTitle.value, summary: editSummary.value }
      : item
  ))

  try {
    const patchResult = await patchStory(store.storyId, { outline: nextOutline })
    if (!patchResult) throw new Error('patch story failed')
    store.updateOutlineEpisode(epNum, editTitle.value, editSummary.value)
    editingEp.value = null
    const res = await refineStory(
      store.storyId,
      'episode',
      `第${epNum}集剧情从「${oldSummary}」改为「${editSummary.value}」`
    )
    if (res) store.applyRefine(res)
  } catch (error) {
    console.error('[OutlinePreview] saveEdit 失败:', error)
  }
}

function cancelEdit() {
  editingEp.value = null
}

function startEditChar(c) {
  editingChar.value = getCharacterKey(c)
  editCharDesc.value = c.description
}

async function saveEditChar(character) {
  if (!character?.id) {
    return
  }
  const key = character.id
  const c = findCharacterByRef(store.characters, character)
  const oldDesc = c ? c.description : ''
  const nextCharacters = store.characters.map(item => (
    item.id === key
      ? { ...item, description: editCharDesc.value }
      : item
  ))

  try {
    const patchResult = await patchStory(store.storyId, { characters: nextCharacters })
    if (!patchResult) throw new Error('patch story failed')
    store.updateCharacter(key, { description: editCharDesc.value })
    editingChar.value = null
    const res = await refineStory(
      store.storyId,
      'character',
      `角色「${character.name}」描述从「${oldDesc}」改为「${editCharDesc.value}」`
    )
    if (res) store.applyRefine(res)
  } catch (error) {
    console.error('[OutlinePreview] saveEditChar 失败:', error)
  }
}

function cancelEditChar() {
  editingChar.value = null
}

function openCharacterChat(character) {
  selectedCharacter.value = character
  characterChatOpen.value = true
}

function openEpisodeChat(episode) {
  selectedEpisode.value = episode
  episodeChatOpen.value = true
}
</script>

<style scoped src="../style/components/outlinepreview.css"></style>
