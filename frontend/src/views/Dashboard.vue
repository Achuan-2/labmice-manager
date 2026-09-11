<template>
  <div class="dashboard-page">
    <!-- Top Stats Cards -->
    <div class="grid grid-cols-6 gap-4 mb-6">
      <div class="stat-card bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div class="text-xs text-gray-500 font-medium">总小鼠数 (档案)</div>
        <div class="text-2xl font-bold text-gray-800 mt-1">{{ stats.total_mice || 0 }}</div>
        <div class="text-xs text-blue-600 mt-1">包含历史存盘</div>
      </div>

      <div class="stat-card bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div class="text-xs text-gray-500 font-medium">当前在笼小鼠</div>
        <div class="text-2xl font-bold text-blue-600 mt-1">{{ stats.in_cage_mice || 0 }}</div>
        <div class="text-xs text-gray-400 mt-1">分布在各鼠房</div>
      </div>

      <div class="stat-card bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div class="text-xs text-gray-500 font-medium">已被领用小鼠</div>
        <div class="text-2xl font-bold text-green-600 mt-1">{{ stats.claimed_mice || 0 }}</div>
        <div class="text-xs text-gray-400 mt-1">已指定责任人</div>
      </div>

      <div class="stat-card bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div class="text-xs text-gray-500 font-medium">可用未领用小鼠</div>
        <div class="text-2xl font-bold text-amber-600 mt-1">{{ stats.unclaimed_mice || 0 }}</div>
        <div class="text-xs text-gray-400 mt-1">在笼待分配</div>
      </div>

      <div class="stat-card bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div class="text-xs text-gray-500 font-medium">笼位总数</div>
        <div class="text-2xl font-bold text-gray-800 mt-1">{{ stats.total_cages || 0 }}</div>
        <div class="text-xs text-gray-400 mt-1">分布在各鼠房</div>
      </div>

      <div class="stat-card bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div class="text-xs text-gray-500 font-medium">待处理转鼠需求</div>
        <div class="text-2xl font-bold text-purple-600 mt-1">{{ stats.pending_requests_count || 0 }}</div>
        <div class="text-xs text-gray-400 mt-1">申请中及进行中</div>
      </div>
    </div>

    <!-- Room Breakdown Cards -->
    <div class="mb-6">
      <div class="flex items-center justify-between mb-3">
        <div class="text-base font-bold text-gray-800 flex items-center gap-2">
          <span>🏢 各鼠房笼位分布情况</span>
        </div>
        <el-button type="primary" link @click="$router.push('/cages')">
          进入鼠架笼位看板 →
        </el-button>
      </div>

      <div class="grid grid-cols-4 gap-4">
        <div
          v-for="r in stats.rooms || []"
          :key="r.room"
          class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition cursor-pointer"
          @click="$router.push(`/cages?room=${r.room}`)"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="font-bold text-gray-800 text-base">{{ r.room }}</span>
            <div class="flex items-baseline gap-1 shrink-0">
              <span class="text-2xl font-bold text-blue-600">{{ r.cages }}</span>
              <span class="text-xs text-gray-500">个笼位</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pending Transfer Requests -->
    <div class="bg-white p-5 rounded-xl shadow-sm border border-gray-200">
      <div class="flex items-center justify-between mb-4">
        <span class="font-bold text-gray-800 text-base">📋 未处理的转鼠需求及反馈</span>
        <el-button link type="primary" @click="$router.push('/transfer-requests')">查看全部需求 →</el-button>
      </div>
      <el-table
        :data="stats.pending_requests || []"
        size="small"
        stripe
        empty-text="暂无未处理的转鼠需求"
        style="width: 100%"
      >
        <el-table-column prop="request_date" label="申请日期" width="120" />
        <el-table-column prop="demander" label="需求者" width="140">
          <template #default="{ row }">
            <span
              class="px-2 py-0.5 rounded-full text-xs font-semibold border inline-flex items-center gap-1"
              :style="getClaimerTagStyle(row.demander)"
            >
              <span
                class="w-1.5 h-1.5 rounded-full inline-block"
                :style="{ backgroundColor: getClaimerTagStyle(row.demander).color || '#2563eb' }"
              ></span>
              {{ row.demander }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="strain" label="需求品系" min-width="130" />
        <el-table-column prop="age_gender_req" label="年龄 / 性别要求" min-width="150">
          <template #default="{ row }">
            <span class="text-xs text-gray-600">{{ row.age_gender_req || '无要求' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="target_room" label="期望转入鼠房" width="130" />
        <el-table-column prop="cage_count" label="笼位数" width="90" align="center" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === '进行中' ? 'primary' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="feedback" label="反馈" min-width="160">
          <template #default="{ row }">
            <span class="text-xs text-gray-600">{{ row.feedback || '暂无反馈' }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="authStore.isAdmin" label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openApproval(row)">
              审批处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Today's Todos -->
    <div v-if="authStore.isAdmin" class="bg-white p-5 rounded-xl shadow-sm border border-gray-200 mt-6">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <span class="font-bold text-gray-800 text-base">📅 今天待办</span>
          <el-tag v-if="todayTodos.length" size="small" type="danger" round>{{ todayTodos.length }}</el-tag>
        </div>
        <el-button link type="primary" @click="router.push('/todos')">进入待办看板 →</el-button>
      </div>
      <el-table
        v-loading="todosLoading"
        :data="todayTodos"
        size="small"
        stripe
        empty-text="今天没有待处理事项"
        style="width: 100%"
      >
        <el-table-column label="完成" width="70" align="center">
          <template #default="{ row }">
            <el-checkbox
              :model-value="false"
              :disabled="updatingTodoId === row.id"
              @change="completeTodo(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="title" label="待办事项" min-width="260">
          <template #default="{ row }">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-medium text-gray-800">{{ row.title }}</span>
              <el-tag size="small" :type="todoSourceTag(row.source).type" effect="plain">
                {{ todoSourceTag(row.source).label }}
              </el-tag>
              <el-tag v-if="isTodoOverdue(row)" size="small" type="danger">已逾期</el-tag>
            </div>
            <div v-if="row.notes" class="text-xs text-gray-500 mt-1 line-clamp-2">{{ row.notes }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="due_at" label="截止时间" width="155">
          <template #default="{ row }">
            <span class="text-xs" :class="isTodoOverdue(row) ? 'text-red-600 font-medium' : 'text-gray-600'">
              {{ formatTodoDueAt(row.due_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="关联对象" min-width="220">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1">
              <el-button
                v-for="cage in todoCages(row)"
                :key="`cage-${cage.id}`"
                type="primary"
                link
                size="small"
                title="打开笼位进行处理"
                @click="openTodoCage(cage)"
              >
                笼位：{{ cage.room }} · {{ cage.cage_code }}
              </el-button>
              <el-button
                v-for="mouse in todoMice(row)"
                :key="`mouse-${mouse.id}`"
                type="primary"
                link
                size="small"
                title="打开小鼠档案进行处理"
                @click="openTodoMouse(mouse)"
              >
                小鼠：{{ mouse.mouse_code }}
              </el-button>
              <span v-if="!todoCages(row).length && !todoMice(row).length" class="text-xs text-gray-400">-</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <MouseDetailModal
      v-model="showMouseDetail"
      :mouse-id="selectedMouseId"
      :mouse-code="selectedMouseCode"
      :start-in-edit-mode="true"
      @refresh="handleMouseRefresh"
    />
    <CageDetailDialog
      v-model="showCageDetail"
      :cage-id="selectedCageId"
      @refresh="handleCageRefresh"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { statsApi, todosApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClaimerColors } from '@/composables/useClaimerColors'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import CageDetailDialog from '@/components/CageDetailDialog.vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const { getClaimerTagStyle, fetchClaimerColors } = useClaimerColors()

const stats = ref({})
const loading = ref(false)
const todayTodos = ref([])
const todosLoading = ref(false)
const updatingTodoId = ref(null)
const showMouseDetail = ref(false)
const selectedMouseId = ref(null)
const selectedMouseCode = ref('')
const showCageDetail = ref(false)
const selectedCageId = ref(null)

async function loadStats() {
  loading.value = true
  try {
    stats.value = await statsApi.getDashboardStats()
  } catch (e) {
    console.error('Failed to load dashboard stats', e)
  } finally {
    loading.value = false
  }
}

function openApproval(row) {
  router.push({
    path: '/transfer-requests',
    query: { approve: String(row.id) }
  })
}

function todoSourceTag(source) {
  if (source === 'litter_weaning') return { label: '生鼠21天', type: 'warning' }
  if (source === 'mixed_aged') return { label: '混笼40周', type: 'danger' }
  return { label: '手动待办', type: 'primary' }
}

function isTodoOverdue(todo) {
  return Boolean(todo.due_at && todo.due_at.slice(0, 10) < new Date().toLocaleDateString('en-CA'))
}

function formatTodoDueAt(value) {
  return value ? value.replace('T', ' ') : '-'
}

function todoCages(todo) {
  return todo.cages?.length ? todo.cages : (todo.cage ? [todo.cage] : [])
}

function todoMice(todo) {
  return todo.mice?.length ? todo.mice : (todo.mouse ? [todo.mouse] : [])
}

function openTodoCage(cage) {
  selectedCageId.value = cage.id
  showCageDetail.value = true
}

function openTodoMouse(mouse) {
  selectedMouseId.value = mouse.id || null
  selectedMouseCode.value = mouse.mouse_code || ''
  showMouseDetail.value = true
}

async function handleMouseRefresh() {
  await Promise.all([loadTodayTodos(), loadStats()])
  window.dispatchEvent(new Event('todos-updated'))
}

async function handleCageRefresh() {
  await Promise.all([loadTodayTodos(), loadStats()])
  window.dispatchEvent(new Event('todos-updated'))
}

async function loadTodayTodos() {
  if (!authStore.isAdmin) return
  todosLoading.value = true
  try {
    todayTodos.value = await todosApi.listTodos({ bucket: 'today' })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载今天待办失败')
  } finally {
    todosLoading.value = false
  }
}

async function completeTodo(todo) {
  updatingTodoId.value = todo.id
  try {
    await todosApi.updateTodo(todo.id, { status: 'completed' })
    ElMessage.success('待办已完成')
    await loadTodayTodos()
    window.dispatchEvent(new Event('todos-updated'))
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新待办失败')
  } finally {
    updatingTodoId.value = null
  }
}

onMounted(() => {
  fetchClaimerColors()
  loadStats()
  loadTodayTodos()
})
</script>

<style scoped>
.stat-card {
  transition: transform 0.2s;
}
.stat-card:hover {
  transform: translateY(-2px);
}
</style>
