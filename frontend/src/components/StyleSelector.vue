<template>
  <div class="style-selector">
    <button
      v-for="s in styles"
      :key="s.value"
      class="style-btn"
      :class="{ selected: modelValue === s.value }"
      @click="$emit('update:modelValue', s.value)"
    >
      <span class="style-icon">{{ s.icon }}</span>
      <span>{{ s.label }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({ modelValue: String })
defineEmits(['update:modelValue'])

const styles = [
  { value: '现代', label: '现代', icon: '🏙️' },
  { value: '古装', label: '古装', icon: '🏯' },
  { value: '悬疑', label: '悬疑', icon: '🔍' },
  { value: '甜宠', label: '甜宠', icon: '🍬' },
]
</script>

<style scoped>
.style-selector {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.style-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 20px;
  border-radius: 12px;
  background: #fff;
  border: 2px solid #e0e0e0;
  font-size: 14px;
  color: #555;
  transition: all 0.2s;
}
.style-btn:hover {
  border-color: #6c63ff;
  color: #6c63ff;
}
.style-btn.selected {
  border-color: #6c63ff;
  background: #f0eeff;
  color: #6c63ff;
  font-weight: 600;
}
.style-icon {
  font-size: 24px;
}
</style>
