<template>
  <div class="transfers-page">
    <!-- Header -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">变动日志</div>
        <div class="text-xs text-gray-500 mt-1">
          记录新增小鼠、领取人指定、鼠房转移、换笼与状态变更，方便追溯
        </div>
      </div>

      <div class="flex items-center gap-3">
        <el-input
          v-model="filters.claimer_name"
          placeholder="按领取人筛选"
          clearable
          style="width: 160px"
          @keyup.enter="searchTransfers"
          @clear="searchTransfers"
        />
        <el-select v-model="filters.action_type" clearable placeholder="全部操作类型" style="width: 140px" @change="searchTransfers">
          <el-option label="新增小鼠" value="新增小鼠" />
          <el-option label="设置领取人" value="设置领取人" />
          <el-option label="转鼠/领用" value="转鼠/领用" />
          <el-option label="转鼠审批" value="转鼠/审批处理" />
          <el-option label="撤销分配/回笼" value="撤销分配/回笼" />
          <el-option label="转房/换笼" value="转房/换笼" />
          <el-option label="批量换笼" value="批量换笼" />
          <el-option label="交付领取人" value="转鼠/交付领取人" />
          <el-option label="状态变更" value="状态变更" />
        </el-select>
        <el-button type="primary" @click="searchTransfers">查询</el-button>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table v-loading="loading" :data="transfers" stripe style="width: 100%">
        <el-table-column prop="date" label="操作日期" width="120">
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-600">{{ row.date || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="action_type" label="操作类型" width="130">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.action_type.includes('新增') || row.action_type.includes('设置') ? 'success' : (row.action_type.includes('转') ? 'primary' : 'info')"
            >
              {{ row.action_type }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="claimer_name" label="领取人 / 需求者" width="140">
          <template #default="{ row }">
            <el-tag
              v-if="row.claimer_name"
              size="small"
              :style="getClaimerTagStyle(row.claimer_name)"
              class="font-medium border"
            >
              👤 {{ row.claimer_name }}
            </el-tag>
            <span v-else class="text-gray-400 text-xs">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="mouse_count" label="数量" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.mouse_count || 1 }} 只</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="mouse_codes" label="小鼠耳标 (点击查档案)" min-width="220">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1">
              <span
                v-for="code in splitMouseCodes(row.mouse_codes)"
                :key="code"
                class="inline-flex items-center gap-1 cursor-pointer font-mono text-xs font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 px-2 py-0.5 rounded border border-blue-200 transition-colors group"
                title="点击查看小鼠完整档案与系谱"
                @click="openMouseDetail(code)"
              >
                <span>{{ code }}</span>
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="位置变化" min-width="180">
          <template #default="{ row }">
            <div class="text-xs flex items-center gap-1">
              <span class="text-gray-500">{{ row.source_room || (row.action_type === '新增小鼠' ? '新增' : '未记录鼠房') }}</span>
              <span v-if="row.source_cage" class="text-amber-600 font-mono font-bold">({{ row.source_cage }})</span>
              <template v-if="row.target_room || row.target_cage">
                <span class="text-gray-400">→</span>
                <span class="font-bold text-gray-700">{{ row.target_room || '未记录鼠房' }}</span>
                <span v-if="row.target_cage" class="text-amber-600 font-mono font-bold">({{ row.target_cage }})</span>
              </template>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === '已完成' || row.status === '已转' ? 'success' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="operator" label="经办人" width="110" />

        <el-table-column prop="notes" label="备注说明" min-width="160">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.notes || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="p-3 border-t border-gray-100 flex justify-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="page = 1"
        />
      </div>
    </div>

    <!-- Mouse Detail Modal -->
    <MouseDetailModal
      v-model="showMouseDetailModal"
      :mouse-code="selectedMouseCode"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { transfersApi } from '@/api'
import { useClaimerColors } from '@/composables/useClaimerColors'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import { ElMessage } from 'element-plus'

const { getClaimerTagStyle, fetchClaimerColors } = useClaimerColors()

const loading = ref(false)
const transfers = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
let loadRequestId = 0

// Mouse Detail Modal
const showMouseDetailModal = ref(false)
const selectedMouseCode = ref('')

function openMouseDetail(code) {
  selectedMouseCode.value = code.trim()
  showMouseDetailModal.value = true
}

function splitMouseCodes(str) {
  if (!str) return []
  return str.replace(/，/g, ',').replace(/、/g, ',').split(',').map(s => s.trim()).filter(Boolean)
}

const filters = reactive({
  claimer_name: '',
  action_type: ''
})

async function loadTransfers() {
  const requestId = ++loadRequestId
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      claimer_name: filters.claimer_name || undefined,
      action_type: filters.action_type || undefined
    }
    const result = await transfersApi.listTransfers(params)
    if (requestId !== loadRequestId) return
    transfers.value = result.items
    total.value = result.total
  } catch (e) {
    if (requestId === loadRequestId) ElMessage.error('加载变动日志失败')
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

function searchTransfers() {
  if (page.value === 1) {
    loadTransfers()
  } else {
    page.value = 1
  }
}

watch([page, pageSize], loadTransfers)

onMounted(() => {
  fetchClaimerColors()
  loadTransfers()
})
</script>
