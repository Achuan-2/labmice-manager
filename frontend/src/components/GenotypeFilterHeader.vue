<template>
  <el-popover v-model:visible="visible" placement="bottom-start" trigger="click" :width="260" @show="keyword = ''">
    <template #reference>
      <button
        type="button"
        class="genotype-filter-trigger"
        :class="{ 'is-active': modelValue.length > 0 }"
        :aria-label="`${label} 筛选，已选 ${modelValue.length} 项`"
        :aria-expanded="visible"
      >
        <span>{{ label }}</span>
        <el-icon><Filter /></el-icon>
        <span v-if="modelValue.length" class="genotype-filter-count">{{ modelValue.length }}</span>
      </button>
    </template>
    <el-input v-model="keyword" clearable size="small" placeholder="搜索选项" :aria-label="`搜索 ${label} 选项`" />
    <div v-loading="loading && !options.length" class="genotype-filter-options">
      <el-checkbox-group :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
        <el-checkbox v-for="option in filteredOptions" :key="option" :value="option">
          {{ option || '未填写' }}
        </el-checkbox>
      </el-checkbox-group>
      <div v-if="!loading && !filteredOptions.length" class="genotype-filter-empty">无匹配选项</div>
    </div>
    <div class="genotype-filter-footer">
      <span>已选 {{ modelValue.length }} 项</span>
      <el-button link type="primary" size="small" :disabled="!modelValue.length" @click="emit('update:modelValue', [])">清除筛选</el-button>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Filter } from '@element-plus/icons-vue'

const props = defineProps({
  label: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])
const visible = ref(false)
const keyword = ref('')
const filteredOptions = computed(() => {
  const search = keyword.value.trim().toLocaleLowerCase()
  return props.options.filter(option => (option || '未填写').toLocaleLowerCase().includes(search))
})
</script>

<style scoped>
.genotype-filter-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  white-space: nowrap;
  cursor: pointer;
}

.genotype-filter-trigger:hover,
.genotype-filter-trigger.is-active {
  color: var(--el-color-primary);
}

.genotype-filter-count {
  padding: 0 4px;
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  font-size: 11px;
  line-height: 18px;
}

.genotype-filter-options {
  min-height: 44px;
  max-height: 240px;
  margin: 8px 0;
  overflow-y: auto;
}

.genotype-filter-options :deep(.el-checkbox-group) {
  display: flex;
  flex-direction: column;
}

.genotype-filter-options :deep(.el-checkbox) {
  height: auto;
  min-height: 30px;
  margin-right: 0;
}

.genotype-filter-options :deep(.el-checkbox__label) {
  white-space: normal;
  overflow-wrap: anywhere;
}

.genotype-filter-empty {
  padding: 10px 0;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.genotype-filter-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
