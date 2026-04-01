<template>
  <div v-if="show" class="overlay" @click.self="close">
    <div class="modal">
      <div class="modal-icon">{{ type === 'invalid' ? '❌' : '⚠️' }}</div>
      <div class="modal-title">{{ title }}</div>
      <div class="modal-body">{{ message }}</div>
      <div class="modal-actions">
        <button class="cancel-btn" @click="close">关闭</button>
        <button class="confirm-btn" @click="goSettings">前往设置</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

defineProps({
  show: Boolean,
  title: String,
  message: String,
  type: { type: String, default: 'missing' }, // 'missing' | 'invalid'
})
const emit = defineEmits(['close'])
const router = useRouter()

function close() { emit('close') }
function goSettings() { emit('close'); router.push('/settings') }
</script>

<style scoped src="../style/components/apikeymodal.css"></style>
