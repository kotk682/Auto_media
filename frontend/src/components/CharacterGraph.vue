<template>
  <div class="graph-wrap">
    <div class="graph-title">人物关系图谱</div>
    <svg :viewBox="`0 0 ${W} ${H}`" class="graph-svg">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="#a78bfa" />
        </marker>
      </defs>

      <!-- 连线 + 标签 -->
      <g v-for="(rel, i) in relationships" :key="i">
        <line
          :x1="edgePos(rel).x1" :y1="edgePos(rel).y1"
          :x2="edgePos(rel).x2" :y2="edgePos(rel).y2"
          class="edge"
          marker-end="url(#arrow)"
        />
        <rect
          :x="(edgePos(rel).x1 + edgePos(rel).x2) / 2 - labelWidth(rel.label) / 2"
          :y="(edgePos(rel).y1 + edgePos(rel).y2) / 2 - 9"
          :width="labelWidth(rel.label)"
          height="16"
          rx="4"
          class="edge-label-bg"
        />
        <text
          :x="(edgePos(rel).x1 + edgePos(rel).x2) / 2"
          :y="(edgePos(rel).y1 + edgePos(rel).y2) / 2 + 3"
          class="edge-label"
        >{{ truncate(rel.label, 5) }}</text>
      </g>

      <!-- 节点 -->
      <g v-for="(ch, i) in characters" :key="ch.name" class="node-group">
        <circle :cx="positions[i].x" :cy="positions[i].y" :r="NODE_R" class="node-circle" />
        <text :x="positions[i].x" :y="positions[i].y + 1" class="node-name">
          {{ truncate(ch.name, 4) }}
        </text>
        <text :x="positions[i].x" :y="positions[i].y + NODE_R + 13" class="node-role">
          {{ truncate(ch.role, 5) }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  characters: { type: Array, default: () => [] },
  relationships: { type: Array, default: () => [] },
})

// 动态画布：人物越多越大
const n = computed(() => props.characters.length)
const NODE_R = computed(() => n.value <= 3 ? 34 : n.value <= 5 ? 30 : 26)
const LAYOUT_R = computed(() => n.value <= 2 ? 80 : n.value <= 4 ? 100 : n.value <= 6 ? 115 : 130)
const W = computed(() => (LAYOUT_R.value + NODE_R.value + 20) * 2)
const H = computed(() => W.value)
const CX = computed(() => W.value / 2)
const CY = computed(() => H.value / 2)

const positions = computed(() => {
  return props.characters.map((_, i) => {
    const angle = (2 * Math.PI * i) / n.value - Math.PI / 2
    return {
      x: CX.value + LAYOUT_R.value * Math.cos(angle),
      y: CY.value + LAYOUT_R.value * Math.sin(angle),
    }
  })
})

function pos(name) {
  const i = props.characters.findIndex(c => c.name === name)
  return i >= 0 ? positions.value[i] : { x: CX.value, y: CY.value }
}

function edgePos(rel) {
  const s = pos(rel.source)
  const t = pos(rel.target)
  const dx = t.x - s.x
  const dy = t.y - s.y
  const dist = Math.sqrt(dx * dx + dy * dy) || 1
  const ux = dx / dist
  const uy = dy / dist
  const nr = NODE_R.value
  return {
    x1: s.x + ux * (nr + 2),
    y1: s.y + uy * (nr + 2),
    x2: t.x - ux * (nr + 10),
    y2: t.y - uy * (nr + 10),
  }
}

function labelWidth(text) {
  return Math.min(text.length, 5) * 11 + 10
}

function truncate(str, max) {
  return str && str.length > max ? str.slice(0, max) + '…' : str
}
</script>

<style scoped>
.graph-wrap {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.graph-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 8px; }
.graph-svg { width: 100%; height: auto; display: block; }
.edge { stroke: #a78bfa; stroke-width: 1.5; }
.edge-label-bg { fill: #f0eeff; }
.edge-label { font-size: 11px; fill: #6c63ff; text-anchor: middle; dominant-baseline: middle; }
.node-circle { fill: #6c63ff; transition: fill 0.2s; }
.node-group:hover .node-circle { fill: #5a52e0; }
.node-name { font-size: 12px; fill: #fff; font-weight: 700; text-anchor: middle; dominant-baseline: middle; }
.node-role { font-size: 11px; fill: #888; text-anchor: middle; }
</style>
