<template>
  <el-popover v-model:visible="visible" placement="bottom-start" trigger="click" :width="300">
    <template #reference>
      <button type="button" class="column-menu-trigger" :class="{ 'is-active': filtered || sortOrder }"
        :aria-label="`${label}列菜单`" :aria-expanded="visible">
        <span>{{ label }}</span>
        <Filter v-if="filtered" :size="14" aria-label="已筛选" />
        <ArrowUp v-if="sortOrder === 'asc'" :size="14" aria-label="升序" />
        <ArrowDown v-else-if="sortOrder === 'desc'" :size="14" aria-label="降序" />
        <ChevronDown v-else :size="14" class="menu-chevron" aria-hidden="true" />
      </button>
    </template>

    <div class="column-menu" :aria-label="`${label}操作菜单`">
      <button type="button" class="column-menu-action" :aria-expanded="showFilter" @click="showFilter = !showFilter">
        <Filter :size="16" />筛选<ChevronDown :size="14" class="trailing-icon" />
      </button>
      <form v-if="showFilter" class="column-filter-form" @submit.prevent="applyFilter">
        <div v-for="control in controls" :key="control.key" class="column-filter-control">
          <span>{{ control.label }}</span>
          <el-select v-if="control.type === 'select'" v-model="draft[control.key]" :multiple="control.multiple"
            filterable clearable :teleported="false" :reserve-keyword="false" :placeholder="control.placeholder || '全部'" :aria-label="control.label">
            <el-option v-for="option in control.options" :key="String(option.value)" :value="option.value" :label="option.label" />
          </el-select>
          <el-date-picker v-else-if="control.type === 'date'" v-model="draft[control.key]" type="date"
            value-format="YYYY-MM-DD" :teleported="false" :placeholder="control.label" :aria-label="control.label" style="width: 100%" />
          <el-input v-else v-model="draft[control.key]" clearable :placeholder="control.placeholder || '输入筛选内容'"
            :aria-label="control.label" />
        </div>
        <div class="column-filter-footer">
          <el-button size="small" :disabled="!filtered" @click="clearFilter">清除此列</el-button>
          <el-button size="small" type="primary" native-type="submit">应用筛选</el-button>
        </div>
      </form>
      <div class="column-menu-divider" />
      <button type="button" class="column-menu-action" :class="{ selected: sortOrder === 'asc' }" @click="setSort('asc')">
        <ArrowUp :size="16" />升序
      </button>
      <button type="button" class="column-menu-action" :class="{ selected: sortOrder === 'desc' }" @click="setSort('desc')">
        <ArrowDown :size="16" />降序
      </button>
      <button type="button" class="column-menu-action" @click="resetSort">
        <ListOrdered :size="16" />恢复录入顺序
      </button>
      <div v-if="anyFiltered" class="column-menu-divider" />
      <button v-if="anyFiltered" type="button" class="column-menu-action" @click="resetFilters">
        <RotateCcw :size="16" />清除全部筛选
      </button>
    </div>
  </el-popover>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ArrowDown, ArrowUp, ChevronDown, Filter, ListOrdered, RotateCcw } from 'lucide-vue-next'

const props = defineProps({
  label: { type: String, required: true },
  controls: { type: Array, required: true },
  modelValue: { type: Object, required: true },
  filtered: Boolean,
  anyFiltered: Boolean,
  sortOrder: { type: String, default: '' },
})
const emit = defineEmits(['filter', 'sort', 'reset-sort', 'reset-filters'])
const visible = ref(false)
const showFilter = ref(false)
const draft = ref({})
watch(visible, value => { if (value) openMenu() })

function openMenu() {
  draft.value = Object.fromEntries(Object.entries(props.modelValue).map(([key, value]) => [key, Array.isArray(value) ? [...value] : value]))
  showFilter.value = false
}

function applyFilter() {
  emit('filter', draft.value)
  visible.value = false
}

function clearFilter() {
  draft.value = Object.fromEntries(props.controls.map(control => [control.key, control.multiple ? [] : null]))
  applyFilter()
}

function setSort(order) {
  emit('sort', order)
  visible.value = false
}

function resetSort() {
  emit('reset-sort')
  visible.value = false
}

function resetFilters() {
  emit('reset-filters')
  visible.value = false
}
</script>

<style scoped>
.column-menu-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.column-menu-trigger svg { flex-shrink: 0; }
.column-menu-trigger:hover, .column-menu-trigger.is-active { color: var(--el-color-primary); }
.menu-chevron { opacity: .55; }
.column-menu-action {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--el-text-color-regular);
  font: inherit;
  cursor: pointer;
}
.column-menu-action:hover, .column-menu-action.selected { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.trailing-icon { margin-left: auto; }
.column-menu-divider { margin: 6px 0; border-top: 1px solid var(--el-border-color-lighter); }
.column-filter-form { padding: 8px 10px; }
.column-filter-control { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; font-size: 12px; }
.column-filter-footer { display: flex; justify-content: space-between; gap: 8px; }
</style>
