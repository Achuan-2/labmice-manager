<template>
  <div class="claimers-page">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between gap-4 flex-wrap">
      <div>
        <div class="text-base font-bold text-gray-800">课题组成员与领取人档案</div>
        <div class="text-xs text-gray-500 mt-1">
          管理实验小鼠责任人，小鼠可直接关联至具体成员，支持统计每位成员的名下小鼠
        </div>
      </div>

      <div class="flex items-center gap-3">
        <el-input
          v-model="searchQuery"
          placeholder="搜索成员姓名 / 角色 / 邮箱 / 电话"
          clearable
          style="width: 250px"
          prefix-icon="Search"
        />
        <el-button v-if="authStore.isAdmin" type="primary" @click="openAddDialog">
          <el-icon class="mr-1"><Plus /></el-icon> 新增成员
        </el-button>
      </div>
    </div>

    <!-- Member Cards Grid -->
    <div v-if="!loading && claimers.length === 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center text-gray-400">
      暂无课题组成员档案，点击上方“新增成员”添加
    </div>

    <div v-else-if="!loading && filteredMembers.length === 0" class="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center text-gray-400">
      未找到与“<span class="text-gray-700 font-semibold">{{ searchQuery }}</span>”相匹配的课题组成员，可清空搜索条件重试
    </div>

    <div v-else v-loading="loading" class="claimers-grid">
      <div
        v-for="c in filteredMembers"
        :key="c.id"
        class="claimer-card bg-white rounded-xl shadow-sm border border-gray-200"
        :style="{ borderTop: '4px solid ' + (c.color || '#2563eb') }"
      >
        <div>
          <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-2 flex-wrap">
              <span
                class="px-2.5 py-0.5 rounded-full text-base font-bold border inline-flex items-center gap-1.5 shadow-2xs"
                :style="{
                  backgroundColor: (c.color || '#2563eb') + '15',
                  color: c.color || '#2563eb',
                  borderColor: (c.color || '#2563eb') + '40'
                }"
              >
                <span
                  class="color-dot rounded-full inline-block"
                  :style="{ backgroundColor: c.color || '#2563eb' }"
                ></span>
                {{ c.name }}
              </span>
              <el-tag size="small" :type="getRoleTagType(c.role)">{{ c.role === '实验管家' ? '管家' : (c.role || '学生') }}</el-tag>
            </div>

            <!-- Mice Count Badge -->
            <el-tag
              size="default"
              class="font-bold border"
              :style="{
                backgroundColor: (c.color || '#2563eb') + '15',
                color: c.color || '#2563eb',
                borderColor: (c.color || '#2563eb') + '35'
              }"
            >
              {{ c.mouse_count }} 只小鼠
            </el-tag>
          </div>

          <div class="claimer-info text-xs text-gray-500 bg-gray-50 rounded-lg flex flex-col gap-1.5">
            <div v-if="c.email" class="flex items-center gap-1.5">
              <span>📧</span>
              <span class="text-gray-400">邮箱:</span>
              <span class="text-gray-700 font-mono">{{ c.email }}</span>
            </div>
            <div v-if="c.phone" class="flex items-center gap-1.5">
              <span>📱</span>
              <span class="text-gray-400">电话:</span>
              <span class="text-gray-700 font-mono">{{ c.phone }}</span>
            </div>
            <div v-if="c.notes" class="flex items-start gap-1.5">
              <span>📝</span>
              <span class="text-gray-400">备注:</span>
              <span class="text-gray-700">{{ c.notes }}</span>
            </div>
            <div v-if="!c.email && !c.phone && !c.notes" class="text-gray-400">
              <span>暂无附加联系信息</span>
            </div>
          </div>
        </div>

        <div class="claimer-footer flex items-center justify-between">
          <el-button
            link
            size="small"
            class="font-bold"
            :style="{ color: c.color || '#2563eb' }"
            @click="viewMemberMice(c)"
          >
            查看其领用小鼠 ({{ c.mouse_count }}) →
          </el-button>

          <div class="flex items-center gap-1">
            <el-button link size="small" type="primary" @click="openEditDialog(c)">编辑信息</el-button>
            <el-popconfirm
              v-if="authStore.isAdmin"
              title="确定删除该成员吗？其名下小鼠将恢复为未分配"
              @confirm="handleDelete(c.id)"
            >
              <template #reference>
                <el-button link size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <!-- Member Mice Drawer -->
    <el-drawer
      v-model="showMiceDrawer"
      size="680px"
      destroy-on-close
    >
      <template #header>
        <div class="flex items-center gap-2">
          <span
            class="px-3 py-1 rounded-full text-sm font-bold border inline-flex items-center gap-1.5"
            :style="{
              backgroundColor: (activeClaimer?.color || '#2563eb') + '20',
              color: activeClaimer?.color || '#2563eb',
              borderColor: (activeClaimer?.color || '#2563eb') + '50'
            }"
          >
            <span class="w-2.5 h-2.5 rounded-full inline-block" :style="{ backgroundColor: activeClaimer?.color || '#2563eb' }"></span>
            {{ activeClaimer?.name || '' }}
          </span>
          <span class="text-sm font-bold text-gray-700">领用的小鼠档案 ({{ activeClaimerMice.length }} 只)</span>
        </div>
      </template>
      <div v-loading="drawerLoading">
        <div class="mb-4 flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center gap-2">
            <span class="text-sm text-gray-500">成员领用小鼠清单</span>
            <el-input
              v-model="miceSearchCode"
              placeholder="筛选耳标 / 品系 / 笼位"
              size="small"
              clearable
              style="width: 190px"
              prefix-icon="Search"
            />
          </div>
          <el-button
            size="small"
            type="primary"
            @click="$router.push(`/mice?owner_name=${activeClaimer?.name}`)"
          >
            在小鼠列表中查看与批处理
          </el-button>
        </div>

        <el-table :data="pagedClaimerMice" size="small" stripe style="width: 100%">
          <el-table-column prop="mouse_code" label="耳标编号 (点击查档案)" width="140">
            <template #default="{ row }">
              <div
                class="inline-flex items-center gap-1 cursor-pointer text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-1.5 py-0.5 rounded transition-colors group"
                title="点击查看小鼠完整档案与系谱"
                @click="openMouseDetail(row)"
              >
                <span class="font-bold font-mono text-xs underline-offset-2 group-hover:underline">
                  {{ row.mouse_code }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="strain" label="品系" min-width="120" />
          <el-table-column prop="gender" label="性别" width="60" align="center">
            <template #default="{ row }">
              <span :class="row.gender === 'M' ? 'text-blue-500 font-bold' : 'text-pink-500 font-bold'">
                {{ row.gender === 'M' ? '♂' : '♀' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="笼位" width="130">
            <template #default="{ row }">
              <div v-if="row.cage_code">
                <el-tag size="small" type="info">{{ row.cage_room }}</el-tag>
                <el-tag size="small" type="warning" class="ml-1 font-mono">{{ row.cage_code }}</el-tag>
              </div>
              <span v-else class="text-gray-400 text-xs">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="claim_purpose" label="用途/备注" min-width="130" />
        </el-table>

        <!-- Pagination -->
        <div v-if="filteredClaimerMice.length > 0" class="mt-4 flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-gray-100">
          <span class="text-xs text-gray-500">
            显示第 {{ (miceCurrentPage - 1) * micePageSize + 1 }} - {{ Math.min(miceCurrentPage * micePageSize, filteredClaimerMice.length) }} 只，共 {{ filteredClaimerMice.length }} 只
          </span>
          <el-pagination
            v-model:current-page="miceCurrentPage"
            v-model:page-size="micePageSize"
            :page-sizes="[10, 15, 25, 50]"
            :total="filteredClaimerMice.length"
            layout="sizes, prev, pager, next"
            size="small"
            background
          />
        </div>
      </div>
    </el-drawer>

    <!-- Add/Edit Member Dialog -->
    <el-dialog
      v-model="showMemberDialog"
      :title="isEdit ? (authStore.isAdmin ? `编辑成员 - ${memberForm.name}` : `编辑联系信息 - ${memberForm.name}`) : '新增课题组成员'"
      width="480px"
    >
      <el-form :model="memberForm" label-width="90px">
        <el-form-item label="姓名" required>
          <el-input
            v-model="memberForm.name"
            :disabled="isEdit && !authStore.isAdmin"
            placeholder=""
          />
          <div v-if="isEdit && !authStore.isAdmin" class="text-[11px] text-gray-400 mt-1">
            * 成员姓名如需修改请联系管理员
          </div>
        </el-form-item>

        <el-form-item label="身份/角色">
          <el-select
            v-model="memberForm.role"
            :disabled="isEdit && !authStore.isAdmin"
            style="width: 100%"
            filterable
            allow-create
            default-first-option
          >
            <el-option label="学生" value="学生" />
            <el-option label="博士后" value="博士后" />
            <el-option label="科研助理" value="科研助理" />
            <el-option label="管家" value="管家" />
            <el-option label="PI / 导师" value="PI / 导师" />
          </el-select>
        </el-form-item>

        <el-form-item label="联系邮箱">
          <el-input
            v-model="memberForm.email"
            placeholder="如 xxx@fudan.edu.cn"
            clearable
          >
            <template #prefix>
              <span class="text-gray-400">📧</span>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="联系电话">
          <el-input
            v-model="memberForm.phone"
            placeholder="手机号或分机号，如 13800138000"
            clearable
          >
            <template #prefix>
              <span class="text-gray-400">📱</span>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="标识颜色">
          <div class="flex items-center gap-3">
            <el-color-picker
              v-model="memberForm.color"
              :predefine="PRESET_COLORS"
              :disabled="isEdit && !authStore.isAdmin"
            />
            <span class="text-xs text-gray-400">
              {{ isEdit && !authStore.isAdmin ? '（专属识别色由管理员配置）' : '（用于小鼠档案、笼位等处的成员识别色）' }}
            </span>
          </div>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="memberForm.notes"
            type="textarea"
            :rows="2"
            placeholder="研究课题、所属子课题组或联系说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMemberDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMemberForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- Mouse Detail Modal -->
    <MouseDetailModal
      v-model="showMouseDetailModal"
      :mouse-code="selectedMouseCode"
      :mouse-id="selectedMouseId"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { membersApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useMemberColors, PRESET_COLORS } from '@/composables/useClaimerColors'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const { fetchClaimerColors } = useMemberColors()

const loading = ref(false)
const claimers = ref([])
const searchQuery = ref('')

const filteredMembers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return claimers.value
  return claimers.value.filter(c => {
    const name = (c.name || '').toLowerCase()
    const role = (c.role === '实验管家' ? '管家' : (c.role || '学生')).toLowerCase()
    const email = (c.email || '').toLowerCase()
    const phone = (c.phone || '').toLowerCase()
    const notes = (c.notes || '').toLowerCase()
    return name.includes(q) || role.includes(q) || email.includes(q) || phone.includes(q) || notes.includes(q)
  })
})
const showMiceDrawer = ref(false)
const drawerLoading = ref(false)
const activeClaimer = ref(null)
const activeClaimerMice = ref([])
const miceSearchCode = ref('')
const miceCurrentPage = ref(1)
const micePageSize = ref(15)

const filteredClaimerMice = computed(() => {
  const q = miceSearchCode.value.trim().toLowerCase()
  if (!q) return activeClaimerMice.value
  return activeClaimerMice.value.filter(m => {
    const code = (m.mouse_code || '').toLowerCase()
    const strain = (m.strain || '').toLowerCase()
    const cage = (m.cage_code || '').toLowerCase()
    const room = (m.cage_room || '').toLowerCase()
    const purpose = (m.claim_purpose || '').toLowerCase()
    return code.includes(q) || strain.includes(q) || cage.includes(q) || room.includes(q) || purpose.includes(q)
  })
})

const pagedClaimerMice = computed(() => {
  const start = (miceCurrentPage.value - 1) * micePageSize.value
  return filteredClaimerMice.value.slice(start, start + micePageSize.value)
})

watch([miceSearchCode, micePageSize], () => {
  miceCurrentPage.value = 1
})

watch(showMiceDrawer, (val) => {
  if (!val) {
    activeClaimerMice.value = []
    miceSearchCode.value = ''
    miceCurrentPage.value = 1
  }
})

// Mouse Detail Modal
const showMouseDetailModal = ref(false)
const selectedMouseCode = ref('')
const selectedMouseId = ref(null)

function openMouseDetail(row) {
  selectedMouseCode.value = row.mouse_code
  selectedMouseId.value = row.id || null
  showMouseDetailModal.value = true
}

function getRoleTagType(role) {
  if (!role) return 'info'
  if (role.includes('管家')) return 'warning'
  if (role.includes('PI') || role.includes('导师')) return 'danger'
  if (role.includes('助理') || role.includes('博士后')) return 'primary'
  return 'info'
}

const showMemberDialog = ref(false)
const isEdit = ref(false)
const currentEditId = ref(null)

const memberForm = reactive({
  name: '',
  role: '学生',
  email: '',
  phone: '',
  color: PRESET_COLORS[0],
  notes: ''
})

async function loadClaimers() {
  loading.value = true
  try {
    claimers.value = await membersApi.listMembers()
    fetchClaimerColors()
  } catch (e) {
    ElMessage.error('加载成员列表失败')
  } finally {
    loading.value = false
  }
}

async function viewMemberMice(c) {
  activeClaimer.value = c
  miceSearchCode.value = ''
  miceCurrentPage.value = 1
  showMiceDrawer.value = true
  drawerLoading.value = true
  try {
    const res = await membersApi.getMemberMice(c.id)
    activeClaimerMice.value = res.items || []
  } catch (e) {
    ElMessage.error('加载成员小鼠失败')
  } finally {
    drawerLoading.value = false
  }
}

function openAddDialog() {
  isEdit.value = false
  currentEditId.value = null
  const usedColors = claimers.value.map(c => c.color).filter(Boolean)
  const unused = PRESET_COLORS.filter(col => !usedColors.includes(col))
  const autoColor = unused.length > 0
    ? unused[Math.floor(Math.random() * unused.length)]
    : PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)]

  Object.assign(memberForm, {
    name: '',
    role: '学生',
    email: '',
    phone: '',
    color: autoColor,
    notes: ''
  })
  showMemberDialog.value = true
}

function openEditDialog(c) {
  isEdit.value = true
  currentEditId.value = c.id
  const role = c.role === '实验管家' ? '管家' : (c.role || '学生')
  Object.assign(memberForm, {
    name: c.name,
    role: role,
    email: c.email || '',
    phone: c.phone || '',
    color: c.color || PRESET_COLORS[0],
    notes: c.notes || ''
  })
  showMemberDialog.value = true
}

async function submitMemberForm() {
  if (!memberForm.name.trim()) {
    ElMessage.warning('请输入姓名')
    return
  }
  if (memberForm.role === '实验管家') {
    memberForm.role = '管家'
  }
  try {
    if (isEdit.value) {
      await membersApi.updateMember(currentEditId.value, memberForm)
      ElMessage.success('成员信息已更新')
    } else {
      await membersApi.createMember(memberForm)
      ElMessage.success('成员已添加')
    }
    showMemberDialog.value = false
    loadClaimers()
    fetchClaimerColors()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDelete(id) {
  try {
    await membersApi.deleteMember(id)
    ElMessage.success('成员已删除')
    loadClaimers()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadClaimers()
})
</script>

<style scoped>
.claimers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.claimer-card {
  padding: 20px;
  background-color: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.claimer-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.claimer-info {
  background-color: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  padding: 10px 12px;
  margin: 14px 0 16px;
  font-size: 12px;
  line-height: 1.6;
}

.claimer-footer {
  padding-top: 14px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>

