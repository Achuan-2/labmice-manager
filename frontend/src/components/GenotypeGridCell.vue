<template>
  <div
    class="genotype-grid-cell"
    :class="{ 'is-active': active && editable, 'is-fill-range': inFillRange, 'is-editable': editable }"
    :title="editable ? `${editOnClick ? '点击' : '双击'}填写${label}；拖动右下角方块向下填充` : ''"
    @click="handleClick"
    @dblclick="startEdit"
    @pointerenter="emit('fill-enter')"
  >
    <el-date-picker
      v-if="editing && editorType === 'date'"
      ref="input"
      v-model="draft"
      class="genotype-cell-input"
      type="date"
      value-format="YYYY-MM-DD"
      :placeholder="`选择${label}`"
      size="small"
      @change="finishEdit"
      @blur="finishDateEdit"
      @keydown.esc.stop="editing = false"
    />
    <el-select
      v-else-if="editing && editorType === 'select'"
      ref="input"
      v-model="draft"
      class="genotype-cell-input"
      :placeholder="`选择${label}`"
      size="small"
      :clearable="clearable"
      filterable
      automatic-dropdown
      @change="finishEdit"
      @visible-change="visible => { if (!visible) finishEdit() }"
      @keydown.esc.stop="editing = false"
    >
      <el-option v-for="option in options" :key="option.value" :value="option.value" :label="option.label" />
    </el-select>
    <el-autocomplete
      v-else-if="editing"
      ref="input"
      v-model="draft"
      class="genotype-cell-input"
      :fetch-suggestions="suggestions"
      :maxlength="maxLength"
      :placeholder="`填写或选择${label}`"
      size="small"
      @select="finishEdit"
      @blur="finishEdit"
      @keydown.enter.stop.prevent="finishEdit"
      @keydown.esc.stop="editing = false"
    />
    <template v-else>
      <slot>
        <el-tag v-if="value" size="small" :type="tagType">{{ value }}</el-tag>
        <span v-else class="text-gray-300 text-xs">-</span>
      </slot>
      <button
        v-if="showEditButton && editable && !disabled"
        type="button"
        class="genotype-edit-button"
        :aria-label="`编辑${label}`"
        @click.stop="startEdit"
        @dblclick.stop
      >编辑</button>
      <button
        v-if="editable && active && !disabled"
        type="button"
        class="genotype-fill-handle"
        :aria-label="`拖动向下填充${label}`"
        :title="`拖动向下填充${label}`"
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
  label: { type: String, default: '基因型' },
  editorType: { type: String, default: 'genotype' },
  maxLength: { type: Number, default: 64 },
  showEditButton: Boolean,
  editOnClick: Boolean,
  clearable: { type: Boolean, default: true },
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
  const defaults = props.editorType === 'genotype' ? ['纯合子', '杂合子', '野生型', '阳性', '阴性', 'HOM', 'HET', 'WT'] : []
  const values = [...new Set([...props.options, ...defaults])]
  callback(values.filter(value => value && value.toLowerCase().includes(query.toLowerCase())).map(value => ({ value })))
}

async function startEdit() {
  if (editing.value || !props.editable || props.disabled) return
  emit('activate')
  draft.value = props.value || ''
  editing.value = true
  await nextTick()
  input.value?.focus()
}

function handleClick() {
  emit('activate')
  if (props.editOnClick) startEdit()
}

function finishEdit() {
  if (!editing.value) return
  editing.value = false
  const value = (draft.value || '').trim()
  if (value !== (props.value || '').trim()) emit('save', value)
}

async function finishDateEdit() {
  // The date picker parses typed dates after emitting blur; let its model settle first.
  await nextTick()
  finishEdit()
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
.genotype-cell-input { width: 100%; min-width: 0; }
.genotype-edit-button {
  margin-left: auto;
  padding: 2px 4px;
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: #409eff;
  font-size: 12px;
  cursor: pointer;
}
</style>
