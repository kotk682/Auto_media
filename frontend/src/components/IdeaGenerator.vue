<template>
  <div class="generator">
    <div class="gen-title">组合灵感生成器</div>

    <div class="dimensions">
      <div v-for="dim in dimensions" :key="dim.key" class="dim-block">
        <div class="dim-header">
          <span class="dim-label">{{ dim.label }}</span>
          <button class="dice-btn" @click="randomDim(dim)" title="随机">🎲</button>
        </div>
        <div class="dim-options">
          <button
            v-for="opt in dim.options"
            :key="opt"
            class="dim-opt"
            :class="{ selected: selected[dim.key] === opt }"
            @click="select(dim.key, opt)"
          >{{ opt }}</button>
        </div>
      </div>
    </div>

    <div class="gen-actions">
      <button class="random-all-btn" @click="randomAll">🎲 全部随机</button>
      <button class="gen-btn" :disabled="!canGenerate" @click="generate">生成灵感 →</button>
    </div>

    <div v-if="preview" class="preview">{{ preview }}</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['apply'])

const dimensions = [
  {
    key: 'character',
    label: '人物身份',
    options: ['外卖小哥', '落魄千金', '退役特种兵', '冷酷总裁', '女扮男装刺客', '废柴修仙者', '顶流明星', '孤儿院少年', '法医', '星际佣兵', '御厨', '女帝', '黑客', '流浪歌手', '私家侦探', '豪门继承人', '落魄书生', '神秘杀手', '天才少女', '末世幸存者'],
  },
  {
    key: 'era',
    label: '时代背景',
    options: ['现代都市', '古代架空', '近未来赛博', '末世废土', '修仙界', '星际联邦', '民国乱世', '架空王朝', '蒸汽朋克', '异世大陆', '平行宇宙', '海底文明', '后启示录', '魔法学院'],
  },
  {
    key: 'setting',
    label: '特殊设定',
    options: ['失忆', '穿越', '觉醒异能', '女扮男装', '替身', '卧底', '系统附身', '灵魂互换', '时间循环', '双重身份', '重生复仇', '契约婚姻', '身份互换', '诅咒缠身', '绑定命运', '隐藏血脉'],
  },
  {
    key: 'conflict',
    label: '核心冲突',
    options: ['身份揭穿', '豪门恩怨', '复仇逆袭', '阴谋对抗', '禁忌之恋', '争夺继承权', '生死追杀', '权力游戏', '家族秘密', '背叛与救赎', '夺位之争', '跨越阶级', '组织内斗', '真相追查', '守护与牺牲'],
  },
  {
    key: 'tone',
    label: '情感基调',
    options: ['甜宠', '虐恋', '热血成长', '黑色幽默', '悬疑烧脑', '治愈温情', '爽文逆袭', '虐心催泪', '轻松搞笑', '暗黑压抑', '燃系热血', '细水长流', '刀刀见血', '先虐后甜'],
  },
  {
    key: 'scene',
    label: '关键场景',
    options: ['合租同屋', '假扮恋人', '被迫合作', '流落街头', '卧底潜伏', '逃婚出走', '意外相遇', '重回故地', '绝境求生', '豪门宴会', '荒岛困境', '监狱同牢', '战场重逢', '密室逃脱', '末日避难所', '皇宫深处'],
  },
]

const selected = ref({})
const preview = ref('')

const canGenerate = computed(() => Object.keys(selected.value).length >= 3)

function select(key, opt) {
  selected.value = { ...selected.value, [key]: opt }
  preview.value = ''
}

function randomDim(dim) {
  const opt = dim.options[Math.floor(Math.random() * dim.options.length)]
  selected.value = { ...selected.value, [dim.key]: opt }
  preview.value = ''
}

function randomAll() {
  const next = {}
  for (const dim of dimensions) {
    next[dim.key] = dim.options[Math.floor(Math.random() * dim.options.length)]
  }
  selected.value = next
  preview.value = ''
}

// 把选中的维度组合成一句自然语言灵感
function generate() {
  const s = selected.value
  const parts = []

  if (s.character && s.era) {
    parts.push(`${s.era}里的${s.character}`)
  } else if (s.character) {
    parts.push(`一个${s.character}`)
  } else if (s.era) {
    parts.push(`在${s.era}中`)
  }

  if (s.setting) parts.push(`因${s.setting}`)

  if (s.scene) parts.push(`在${s.scene}的情境下`)

  if (s.conflict) parts.push(`卷入了${s.conflict}的漩涡`)

  if (s.tone) parts.push(`展开一段${s.tone}的故事`)

  const text = parts.join('，') + '。'
  preview.value = text
  emit('apply', text)
}
</script>

<style scoped src="../style/components/ideagenerator.css"></style>
