<template>
  <el-select
    :model-value="modelValue"
    filterable
    allow-create
    clearable
    default-first-option
    :reserve-keyword="false"
    :loading="loading"
    :disabled="disabled"
    :placeholder="placeholder || '请选择已有品系或输入新品系后回车'"
    style="width: 100%"
    @update:model-value="$emit('update:modelValue', $event || '')"
    @visible-change="onVisibleChange"
  >
    <el-option v-for="name in options" :key="name" :label="name" :value="name" />
  </el-select>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { strainsApi } from '@/api'
import { ElMessage } from 'element-plus'

defineProps({
  modelValue: String,
  disabled: {
    type: Boolean,
    default: false
  },
  placeholder: {
    type: String,
    default: ''
  }
})
defineEmits(['update:modelValue'])
const options = ref([])
const loading = ref(false)

async function loadOptions() {
  if (loading.value) return
  loading.value = true
  try {
    const strains = await strainsApi.listStrains()
    options.value = [...new Set(strains.map(strain => strain.name).filter(Boolean))]
  } catch (e) {
    ElMessage.error('加载品系失败，仍可手动输入品系')
  } finally {
    loading.value = false
  }
}

function onVisibleChange(open) {
  if (open) loadOptions()
}

onMounted(loadOptions)
</script>
