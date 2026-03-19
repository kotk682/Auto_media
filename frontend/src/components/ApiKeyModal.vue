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

<style scoped>
.overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 16px;
  padding: 28px 24px;
  max-width: 320px;
  width: 90%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}
.modal-icon { font-size: 32px; margin-bottom: 12px; }
.modal-title { font-size: 16px; font-weight: 700; color: #333; margin-bottom: 8px; }
.modal-body { font-size: 13px; color: #666; line-height: 1.6; margin-bottom: 20px; }
.modal-actions { display: flex; gap: 10px; }
.cancel-btn {
  flex: 1; padding: 10px;
  background: #fff; color: #888;
  border: 1.5px solid #e0e0e0; border-radius: 10px;
  font-size: 14px; cursor: pointer;
}
.cancel-btn:hover { border-color: #aaa; }
.confirm-btn {
  flex: 1; padding: 10px;
  background: #6c63ff; color: #fff;
  border-radius: 10px; font-size: 14px;
  font-weight: 600; cursor: pointer;
}
.confirm-btn:hover { background: #5a52e0; }
</style>
