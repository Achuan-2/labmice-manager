<template>
  <el-dialog :model-value="modelValue" title="Excel 导入结果" width="min(1100px, 95vw)"
    :close-on-click-modal="false" @update:model-value="$emit('update:modelValue', $event)">
    <template v-if="result">
      <el-alert :title="result.message" :type="errors.length ? 'warning' : 'success'" :closable="false" />
      <p class="text-sm text-gray-500 my-3">按记录内容识别重复；同一条记录在本次结果中只统计一次。已有记录仅补充空缺信息，保留已有笼位和领取关系。</p>
      <el-tabs v-model="status">
        <el-tab-pane v-for="tab in tabs" :key="tab.value" :name="tab.value"
          :label="`${tab.label}（${summary[tab.value] || 0}）`" />
        <el-tab-pane v-if="summary.removed" name="removed" :label="`清理无效记录（${summary.removed}）`" />
        <el-tab-pane name="errors" :label="`失败（${errors.length}）`" />
      </el-tabs>
      <template v-if="status === 'errors'">
        <el-empty v-if="!errors.length" description="没有解析失败的数据" />
        <div v-else class="max-h-96 overflow-auto space-y-2">
          <el-alert v-for="(error, index) in errors" :key="index" :title="error" type="error" :closable="false" />
        </div>
      </template>
      <template v-else>
        <el-input v-model="search" placeholder="搜索编号、数据类型、文件名或工作表" clearable class="mb-3" />
        <el-table :data="pageRecords" max-height="420" border empty-text="没有此类记录">
          <el-table-column prop="type" label="数据类型" width="95" />
          <el-table-column prop="identifier" label="编号 / 记录" min-width="240" show-overflow-tooltip />
          <el-table-column label="来源" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.filename }} · {{ row.sheet }}{{ row.row ? ` · 第${row.row}行` : '' }}</template>
          </el-table-column>
          <el-table-column label="处理明细" min-width="240">
            <template #default="{ row }">
              <div v-if="row.changes?.length">
                <div v-for="(change, index) in row.changes" :key="index">
                  {{ change.field }}：{{ displayValue(change.before) }} → {{ displayValue(change.after) }}
                </div>
              </div>
              <span v-else>{{ statusDescriptions[row.status] }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :page-size="50" :total="filteredRecords.length"
          layout="total, prev, pager, next" class="mt-3" />
      </template>
      <div v-if="ignoredSheets.length" class="text-sm text-gray-500 mt-3">
        未导入的参考工作表：{{ ignoredSheets.map(item => `${item.filename} / ${item.sheet}（${item.reason}）`).join('；') }}
      </div>
    </template>
    <template #footer><el-button type="primary" @click="$emit('update:modelValue', false)">关闭</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({ modelValue: Boolean, result: { type: Object, default: null } })
defineEmits(['update:modelValue'])
const tabs = [
  { value: 'added', label: '新增' },
  { value: 'updated', label: '补充/更新' },
  { value: 'skipped', label: '重复跳过' },
]
const statusDescriptions = {
  added: '已新增', skipped: '已存在，跳过重复导入', removed: '已清理无效记录',
}
const status = ref('added')
const search = ref('')
const page = ref(1)
const summary = computed(() => props.result?.details?.report?.summary || {})
const errors = computed(() => props.result?.details?.errors || [])
const ignoredSheets = computed(() => props.result?.details?.report?.ignored_sheets || [])
const filteredRecords = computed(() => {
  const term = search.value.trim().toLowerCase()
  return (props.result?.details?.report?.records || []).filter(record =>
    record.status === status.value &&
    (!term || [record.type, record.identifier, record.filename, record.sheet].some(value => value?.toLowerCase().includes(term))),
  )
})
const pageRecords = computed(() => filteredRecords.value.slice((page.value - 1) * 50, page.value * 50))
watch([status, search], () => { page.value = 1 })
watch(() => props.result, () => {
  status.value = summary.value.added ? 'added' : summary.value.updated ? 'updated' : errors.value.length ? 'errors' : 'skipped'
  search.value = ''
  page.value = 1
})
function displayValue(value) {
  return value === null || value === undefined || value === '' ? '空' : String(value)
}
</script>
