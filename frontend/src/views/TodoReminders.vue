<template>
  <div v-if="!authStore.isAdmin" class="bg-white p-12 text-center rounded-xl border border-gray-200">
    <div class="text-3xl mb-3">🔒</div>
    <div class="text-base font-bold text-gray-800 mb-1">无权限访问</div>
    <div class="text-xs text-gray-500 mb-4">待办提醒仅对管理员开放</div>
    <el-button type="primary" @click="router.push('/')">返回首页</el-button>
  </div>
  <div v-else class="todo-page">
    <div class="todo-header bg-white rounded-xl border border-gray-200 shadow-sm p-4 mb-4">
      <div>
        <div class="text-base font-bold text-gray-800">待办提醒</div>
        <div class="text-xs text-gray-500 mt-1">集中处理生鼠满 21 天、混笼小鼠超过 40 周及手动添加的事项。</div>
      </div>
      <el-button v-if="authStore.isAdmin" type="primary" @click="openCreate">
        <el-icon class="mr-1"><Plus /></el-icon> 添加待办
      </el-button>
    </div>

    <el-tabs v-model="activeTab" class="todo-tabs" @tab-change="loadTodos">
      <el-tab-pane name="today">
        <template #label><span>今日待办 <el-tag size="small" type="danger" round>{{ todayTodos.length }}</el-tag></span></template>
      </el-tab-pane>
      <el-tab-pane name="future">
        <template #label><span>未来待办 <el-tag size="small" type="warning" round>{{ futureTodos.length }}</el-tag></span></template>
      </el-tab-pane>
      <el-tab-pane name="inbox">
        <template #label><span>收集箱 <el-tag size="small" type="info" round>{{ inboxTodos.length }}</el-tag></span></template>
      </el-tab-pane>
    </el-tabs>

    <div v-loading="loading" class="todo-list">
      <el-empty v-if="currentTodos.length === 0" :description="emptyDescription" />
      <template v-if="activeTab === 'future'">
        <section v-for="group in futureGroups" :key="group.key" class="todo-group">
          <div class="todo-group-title">{{ group.label }} <span>{{ group.todos.length }} 条</span></div>
          <article v-for="todo in group.todos" :key="todo.id" class="todo-card bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <div class="todo-check"><el-checkbox :model-value="false" :disabled="!authStore.isAdmin || updatingId === todo.id" @change="completeTodo(todo)" /></div>
            <div class="todo-content">
              <div class="flex flex-wrap items-center gap-2"><span class="font-semibold text-gray-800">{{ todo.title }}</span><el-tag size="small" :type="sourceTag(todo.source).type" effect="plain">{{ sourceTag(todo.source).label }}</el-tag></div>
              <div class="todo-meta mt-2"><span>{{ dueIcon(todo.due_at) }} {{ formatDueAt(todo.due_at) }}</span><el-button v-for="cage in todoCages(todo)" :key="`cage-${cage.id}`" type="primary" link @click="openCage(cage)">笼位：{{ cage.room }} · {{ cage.cage_code }}</el-button><el-button v-for="mouse in todoMice(todo)" :key="`mouse-${mouse.id}`" type="primary" link @click="openMouse(mouse)">小鼠：{{ mouse.mouse_code }}</el-button></div>
              <div v-if="todo.notes" class="todo-notes mt-2">{{ todo.notes }}</div>
            </div>
            <div v-if="authStore.isAdmin" class="todo-actions"><el-button v-if="todo.source === 'manual'" type="primary" link @click="openEdit(todo)">编辑</el-button><el-popconfirm title="确定删除这条待办吗？" @confirm="deleteTodo(todo)"><template #reference><el-button type="danger" link>删除</el-button></template></el-popconfirm></div>
          </article>
        </section>
      </template>
      <article v-else v-for="todo in currentTodos" :key="todo.id" class="todo-card bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        <div class="todo-check">
          <el-checkbox :model-value="false" :disabled="!authStore.isAdmin || updatingId === todo.id" @change="completeTodo(todo)" />
        </div>
        <div class="todo-content">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-semibold text-gray-800">{{ todo.title }}</span>
            <el-tag size="small" :type="sourceTag(todo.source).type" effect="plain">{{ sourceTag(todo.source).label }}</el-tag>
            <el-tag v-if="isOverdue(todo)" size="small" type="danger">已逾期</el-tag>
          </div>
          <div class="todo-meta mt-2">
            <span v-if="todo.due_at">{{ dueIcon(todo.due_at) }} {{ formatDueAt(todo.due_at) }}</span>
            <span v-else>📥 未设置时间</span>
            <el-button v-for="cage in todoCages(todo)" :key="`cage-${cage.id}`" type="primary" link @click="openCage(cage)">笼位：{{ cage.room }} · {{ cage.cage_code }}</el-button>
            <el-button v-for="mouse in todoMice(todo)" :key="`mouse-${mouse.id}`" type="primary" link @click="openMouse(mouse)">小鼠：{{ mouse.mouse_code }}</el-button>
          </div>
          <div v-if="todo.notes" class="todo-notes mt-2">{{ todo.notes }}</div>
        </div>
        <div v-if="authStore.isAdmin" class="todo-actions">
          <el-button v-if="todo.source === 'manual'" type="primary" link @click="openEdit(todo)">编辑</el-button>
          <el-popconfirm title="确定删除这条待办吗？" @confirm="deleteTodo(todo)">
            <template #reference><el-button type="danger" link>删除</el-button></template>
          </el-popconfirm>
        </div>
      </article>
    </div>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑待办' : '添加待办'" width="min(560px, 94vw)" :close-on-click-modal="!saving">
      <el-form :model="form" label-width="90px" :disabled="saving">
        <el-form-item label="待办内容" required>
          <el-input v-model="form.title" maxlength="256" show-word-limit placeholder="输入需要处理的事项" />
        </el-form-item>
        <el-form-item label="待办时间">
          <el-date-picker v-model="form.due_at" type="datetime" value-format="YYYY-MM-DDTHH:mm" format="YYYY-MM-DD HH:mm" placeholder="不设置则进入收集箱" style="width: 100%" />
        </el-form-item>
        <el-form-item label="关联笼位">
          <el-select v-model="form.cage_ids" multiple clearable filterable :reserve-keyword="false" placeholder="可选，可关联多个笼位" style="width: 100%">
            <el-option v-for="cage in cages" :key="cage.id" :label="`${cage.room} · ${cage.cage_code}（${cage.mouse_count || 0}只）`" :value="cage.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联小鼠">
          <el-select v-model="form.mouse_ids" multiple clearable filterable :reserve-keyword="false" placeholder="可选，可关联多只小鼠" style="width: 100%">
            <el-option v-for="mouse in mice" :key="mouse.id" :label="`${mouse.mouse_code} · ${mouse.strain || '未指定品系'}`" :value="mouse.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="4" placeholder="补充处理要求或实验记录" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTodo">保存</el-button>
      </template>
    </el-dialog>

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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { cagesApi, miceApi, todosApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import CageDetailDialog from '@/components/CageDetailDialog.vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const activeTab = ref('today')
const todayTodos = ref([])
const futureTodos = ref([])
const inboxTodos = ref([])
const cages = ref([])
const mice = ref([])
const loading = ref(false)
const saving = ref(false)
const updatingId = ref(null)
const showDialog = ref(false)
const editingId = ref(null)
const showMouseDetail = ref(false)
const selectedMouseId = ref(null)
const selectedMouseCode = ref('')
const showCageDetail = ref(false)
const selectedCageId = ref(null)
const form = reactive({ title: '', due_at: '', notes: '', cage_ids: [], mouse_ids: [] })

const currentTodos = computed(() => activeTab.value === 'today' ? todayTodos.value : activeTab.value === 'inbox' ? inboxTodos.value : futureTodos.value)
const emptyDescription = computed(() => activeTab.value === 'today' ? '今天没有待处理事项' : activeTab.value === 'future' ? '未来没有已安排时间的事项' : '收集箱为空')
const futureGroups = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const dayAfter = new Date(today)
  dayAfter.setDate(dayAfter.getDate() + 2)
  const groups = [
    { key: 'tomorrow', label: '明天', todos: [] },
    { key: 'day-after', label: '后天', todos: [] },
    { key: 'future', label: '未来', todos: [] },
  ]
  for (const todo of futureTodos.value) {
    const due = new Date(`${todo.due_at.slice(0, 10)}T00:00:00`)
    if (due.getTime() === tomorrow.getTime()) groups[0].todos.push(todo)
    else if (due.getTime() === dayAfter.getTime()) groups[1].todos.push(todo)
    else groups[2].todos.push(todo)
  }
  return groups.filter(group => group.todos.length)
})

function notifyTodoChange() {
  window.dispatchEvent(new Event('todos-updated'))
}

function sourceTag(source) {
  if (source === 'litter_weaning') return { label: '生鼠21天', type: 'warning' }
  if (source === 'mixed_aged') return { label: '混笼40周', type: 'danger' }
  return { label: '手动待办', type: 'primary' }
}

function formatDueAt(value) {
  return value ? value.replace('T', ' ') : ''
}

function dueIcon(value) {
  return value?.includes('T') ? '⏰' : '📅'
}

function todoCages(todo) {
  return todo.cages?.length ? todo.cages : (todo.cage ? [todo.cage] : [])
}

function todoMice(todo) {
  return todo.mice?.length ? todo.mice : (todo.mouse ? [todo.mouse] : [])
}

function isOverdue(todo) {
  return todo.due_at && todo.due_at.slice(0, 10) < new Date().toLocaleDateString('en-CA')
}

async function loadTodos() {
  if (!authStore.isAdmin) return
  loading.value = true
  try {
    const todos = await todosApi.listTodos({ bucket: 'all' })
    const today = new Date().toLocaleDateString('en-CA')
    todayTodos.value = todos.filter(todo => todo.due_at && todo.due_at.slice(0, 10) <= today)
    futureTodos.value = todos.filter(todo => todo.due_at && todo.due_at.slice(0, 10) > today)
    inboxTodos.value = todos.filter(todo => !todo.due_at)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载待办失败')
  } finally {
    loading.value = false
  }
}

async function loadRelations() {
  if (!authStore.isAdmin) return
  try {
    const [cageList, mouseResult] = await Promise.all([
      cagesApi.listCages(),
      miceApi.listMice({ page: 1, page_size: 500 }),
    ])
    cages.value = cageList
    mice.value = mouseResult.items || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载笼位和小鼠选项失败')
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { title: '', due_at: '', notes: '', cage_ids: [], mouse_ids: [] })
  showDialog.value = true
}

function openEdit(todo) {
  editingId.value = todo.id
  Object.assign(form, {
    title: todo.title,
    due_at: todo.due_at || '',
    notes: todo.notes || '',
    cage_ids: todo.cage_ids?.length ? [...todo.cage_ids] : (todo.cage_id ? [todo.cage_id] : []),
    mouse_ids: todo.mouse_ids?.length ? [...todo.mouse_ids] : (todo.mouse_id ? [todo.mouse_id] : []),
  })
  showDialog.value = true
}

async function saveTodo() {
  if (!form.title.trim()) return ElMessage.warning('请输入待办内容')
  saving.value = true
  try {
    const payload = { ...form, title: form.title.trim(), due_at: form.due_at || null }
    if (editingId.value) await todosApi.updateTodo(editingId.value, payload)
    else await todosApi.createTodo(payload)
    ElMessage.success(editingId.value ? '待办已更新' : '待办已添加')
    showDialog.value = false
    await loadTodos()
    notifyTodoChange()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存待办失败')
  } finally {
    saving.value = false
  }
}

async function completeTodo(todo) {
  updatingId.value = todo.id
  try {
    await todosApi.updateTodo(todo.id, { status: 'completed' })
    ElMessage.success('待办已完成')
    await loadTodos()
    notifyTodoChange()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新待办失败')
  } finally {
    updatingId.value = null
  }
}

async function deleteTodo(todo) {
  try {
    const result = await todosApi.deleteTodo(todo.id)
    ElMessage.success(result.message || '待办已删除')
    await loadTodos()
    notifyTodoChange()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除待办失败')
  }
}

function openCage(cage) {
  selectedCageId.value = cage.id
  showCageDetail.value = true
}

function openMouse(mouse) {
  selectedMouseId.value = mouse.id
  selectedMouseCode.value = mouse.mouse_code
  showMouseDetail.value = true
}

async function handleMouseRefresh() {
  await Promise.all([loadTodos(), loadRelations()])
  notifyTodoChange()
}

async function handleCageRefresh() {
  await Promise.all([loadTodos(), loadRelations()])
  notifyTodoChange()
}

onMounted(async () => {
  if (!authStore.isAdmin) {
    router.replace('/')
    return
  }
  await Promise.all([loadTodos(), loadRelations()])
})

watch(() => authStore.isAdmin, (isAdmin) => {
  if (!isAdmin) {
    router.replace('/')
  }
})
</script>

<style scoped>
.todo-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.todo-tabs { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 0 16px; margin-bottom: 16px; }
.todo-list { display: flex; flex-direction: column; gap: 12px; min-height: 180px; }
.todo-group { display: flex; flex-direction: column; gap: 10px; }
.todo-group-title { color: #475569; font-size: 14px; font-weight: 700; padding: 4px 2px 0; }
.todo-group-title span { color: #94a3b8; font-size: 12px; font-weight: 500; margin-left: 6px; }
.todo-card { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; gap: 10px; align-items: start; }
.todo-check { padding-top: 2px; }
.todo-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; color: #64748b; font-size: 13px; }
.todo-notes { white-space: pre-wrap; color: #475569; background: #f8fafc; border-radius: 8px; padding: 8px 10px; font-size: 13px; }
.todo-actions { display: flex; align-items: center; }
@media (max-width: 767px) {
  .todo-header { align-items: flex-start; }
  .todo-card { grid-template-columns: 28px minmax(0, 1fr); }
  .todo-actions { grid-column: 2; justify-content: flex-end; }
}
</style>
