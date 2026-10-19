<template>
  <div
    class="genotype-grid-cell"
    :class="{ 'is-active': active && editable, 'is-fill-range': inFillRange, 'is-editable': editable }"
    :title="editable ? '双击填写基因型；拖动右下角方块向下填充' : ''"
    @click="emit('activate')"
    @dblclick="startEdit"
    @pointerenter="emit('fill-enter')"
  >
    <el-autocomplete
      v-if="editing"
      ref="input"
      v-model="draft"
      class="genotype-cell-input"
      :fetch-suggestions="suggestions"
      :maxlength="64"
      placeholder="填写或选择结果"
      size="small"
      @select="finishEdit"
      @blur="finishEdit"
      @keydown.enter.stop.prevent="finishEdit"
      @keydown.esc.stop="editing = false"
    />
    <template v-else>
      <el-tag v-if="value" size="small" :type="tagType">{{ value }}</el-tag>
      <span v-else class="text-gray-300 text-xs">-</span>
      <button
        v-if="editable && active && !disabled"
        type="button"
        class="genotype-fill-handle"
        aria-label="拖动向下填充基因型"
        title="拖动向下填充基因型"
        @click.stop
        @pointerdown.stop.prevent="emit('fill-start', $event)"
      />
    </template>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'

const props = defineProps({
  value: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  tagType: { type: String, default: 'info' },
  editable: Boolean,
  active: Boolean,
  inFillRange: Boolean,
  disabled: Boolean
})
const emit = defineEmits(['activate', 'save', 'fill-start', 'fill-enter'])
const editing = ref(false)
const draft = ref('')
const input = ref(null)

function suggestions(query, callback) {
  const values = [...new Set([...props.options, '纯合子', '杂合子', '野生型', '阳性', '阴性', 'HOM', 'HET', 'WT'])]
  callback(values.filter(value => value && value.toLowerCase().includes(query.toLowerCase())).map(value => ({ value })))
}

async function startEdit() {
  if (!props.editable || props.disabled) return
  draft.value = props.value || ''
  editing.value = true
  await nextTick()
  input.value?.focus()
}

function finishEdit() {
  if (!editing.value) return
  editing.value = false
  if (draft.value.trim() !== (props.value || '').trim()) emit('save', draft.value.trim())
}
</script>

<style scoped>
.genotype-grid-cell {
  position: relative;
  min-height: 32px;
  display: flex;
  align-items: center;
  padding: 4px 6px;
  border: 1px solid transparent;
}
.is-editable { cursor: cell; }
.is-active { border-color: #409eff; }
.is-fill-range { background: #ecf5ff; border-color: #a0cfff; }
.genotype-fill-handle {
  position: absolute;
  right: -3px;
  bottom: -3px;
  width: 8px;
  height: 8px;
  padding: 0;
  border: 1px solid white;
  background: #409eff;
  cursor: crosshair;
  touch-action: none;
  z-index: 1;
}
.genotype-cell-input { width: 100%; }
</style>
