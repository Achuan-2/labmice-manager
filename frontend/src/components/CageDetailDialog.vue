<template>
  <el-dialog v-model="visible" title="查看笼位" width="min(900px, 94vw)" append-to-body :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <div v-loading="loading">
      <template v-if="cage">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div class="font-semibold">{{ cage.room }} · {{ cage.cage_code }} · {{ cage.strain || '未指定品系' }}</div>
          <el-button v-if="authStore.isAdmin" type="primary" plain :disabled="busy" @click="editCage">编辑笼位</el-button>
        </div>
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span class="font-semibold">在笼小鼠（{{ cage.mice.length }} 只）</span>
          <div v-if="authStore.isAdmin" class="flex flex-wrap gap-2">
            <el-button type="success" plain size="small" :disabled="busy || !selectedMice.length" @click="openSetOwner">指定领取人{{ selectedMice.length ? `（${selectedMice.length}）` : '' }}</el-button>
            <el-button type="warning" plain size="small" :disabled="busy || !selectedMice.length" @click="openBatchEdit">批量编辑{{ selectedMice.length ? `（${selectedMice.length}）` : '' }}</el-button>
            <el-button type="primary" plain size="small" :disabled="busy || !selectedMice.length" @click="openMove(selectedMice)">批量换笼{{ selectedMice.length ? `（${selectedMice.length}）` : '' }}</el-button>
            <el-button type="primary" size="small" :disabled="busy" @click="openAdd">新增鼠</el-button>
          </div>
        </div>
        <div class="text-xs text-gray-500 mb-3">点击编号可查看和编辑档案；勾选小鼠可批量指定领取人、编辑或换笼。移除只解除当前笼位关联，小鼠档案、领取人及历史记录均保留。</div>
        <el-table :data="cage.mice" max-height="360" empty-text="当前为空笼" @selection-change="handleSelectionChange">
          <el-table-column v-if="authStore.isAdmin" type="selection" width="44" />
          <el-table-column prop="mouse_code" label="小鼠编号" min-width="105">
            <template #default="{ row }"><el-button type="primary" link class="font-mono font-bold" @click="openMouse(row)">{{ row.mouse_code }}</el-button></template>
          </el-table-column>
          <el-table-column prop="strain" label="品系" min-width="115" />
          <el-table-column prop="gender" label="性别" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.gender === 'M'" size="small" type="primary" effect="light">♂ 雄</el-tag>
              <el-tag v-else-if="row.gender === 'F'" size="small" type="danger" effect="light">♀ 雌</el-tag>
              <el-tag v-else size="small" type="info">未知</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="年龄" width="85">
            <template #default="{ row }">{{ row.age_weeks == null ? '-' : `${row.age_weeks}周` }}</template>
          </el-table-column>
          <el-table-column prop="owner_name" label="领取人" min-width="90" />
          <el-table-column v-if="authStore.isAdmin" label="操作" width="135">
            <template #default="{ row }">
              <el-button type="primary" link :disabled="busy" @click="openMove([row])">换笼</el-button>
              <el-popconfirm :title="`将 ${row.mouse_code} 移出本笼？只清除笼位，小鼠档案将完整保留。`" @confirm="removeMouse(row)">
                <template #reference><el-button type="warning" link :disabled="busy">移除鼠</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        <template v-if="authStore.isAdmin">
          <el-dialog v-model="adding" title="新增鼠" width="min(520px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
            <div class="text-sm text-gray-500 mb-4">添加到：{{ cage.room }} · {{ cage.cage_code }}</div>
            <el-form :model="form" label-width="90px" :disabled="busy">
              <el-form-item label="新增数量" required>
                <el-input-number v-model="form.add_count" :min="1" :max="100" @change="updateMouseCodes" />
              </el-form-item>
              <el-form-item label="起始编号" required>
                <el-input v-model="form.start_code" placeholder="如 Z100" @input="updateMouseCodes" />
                <div class="text-xs text-gray-500">起始编号包含在本批内；输入 Z100、新增 5 只，将生成 Z100 至 Z104。</div>
              </el-form-item>
              <el-form-item label="编号列表" required>
                <el-input v-model="form.mouse_code" type="textarea" :rows="2" placeholder="自动生成后仍可手动调整，多个编号用逗号分隔" />
                <div class="text-xs text-gray-500">以下信息应用于全部新增小鼠，已存在的编号会跳过。</div>
              </el-form-item>
              <el-form-item label="品系"><StrainSelect v-model="form.strain" /></el-form-item>
              <el-form-item label="性别"><el-select v-model="form.gender"><el-option label="雄 (M)" value="M" /><el-option label="雌 (F)" value="F" /><el-option label="未知" value="未知" /></el-select></el-form-item>
              <el-form-item label="出生日期"><el-date-picker v-model="form.dob" type="date" value-format="YYYY-MM-DD" /></el-form-item>
              <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
            </el-form>
            <template #footer>
              <el-button :disabled="busy" @click="adding = false">取消</el-button>
              <el-button type="primary" :loading="busy" @click="addMouse">确认新增到本笼</el-button>
            </template>
          </el-dialog>
        </template>
      </template>
      <el-empty v-else-if="!loading" description="未能加载笼位"><el-button @click="loadCage">重试</el-button></el-empty>
    </div>
    <template #footer><el-button :disabled="busy" @click="visible = false">关闭</el-button></template>
  </el-dialog>

  <SetOwnerDialog v-model="settingOwner" :mice="ownerMice" @success="refreshCage" />

  <el-dialog v-model="editingBatch" :title="`批量编辑小鼠（${selectedMice.length}只）`" width="min(520px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
    <div class="text-sm text-gray-500 mb-4 break-all">已选择：{{ selectedMice.map(mouse => mouse.mouse_code).join('、') }}</div>
    <el-form label-position="left" label-width="140px" :disabled="busy">
      <el-form-item>
        <template #label><el-checkbox v-model="batchEditForm.updateStrain">修改品系</el-checkbox></template>
        <StrainSelect v-model="batchEditForm.strain" :disabled="!batchEditForm.updateStrain" placeholder="选择或输入品系；清空可移除品系" />
      </el-form-item>
      <el-form-item>
        <template #label><el-checkbox v-model="batchEditForm.updateDob">修改出生日期</el-checkbox></template>
        <el-date-picker v-model="batchEditForm.dob" type="date" value-format="YYYY-MM-DD" :disabled="!batchEditForm.updateDob" placeholder="选择日期；清空可移除日期" style="width: 100%" />
      </el-form-item>
      <el-form-item>
        <template #label><el-checkbox v-model="batchEditForm.updateGender">修改性别</el-checkbox></template>
        <el-select v-model="batchEditForm.gender" :disabled="!batchEditForm.updateGender" placeholder="请选择性别" style="width: 100%">
          <el-option label="雄 (M)" value="M" />
          <el-option label="雌 (F)" value="F" />
          <el-option label="未知" value="未知" />
        </el-select>
      </el-form-item>
    </el-form>
    <div class="text-xs text-gray-500">未勾选的字段会保持原值。</div>
    <template #footer><el-button :disabled="busy" @click="editingBatch = false">取消</el-button><el-button type="primary" :loading="busy" @click="submitBatchEdit">确认修改</el-button></template>
  </el-dialog>

  <el-dialog v-model="moving" :title="movingMice.length > 1 ? `批量换笼（${movingMice.length}只）` : `小鼠换笼 - ${movingMice[0]?.mouse_code || ''}`" width="min(460px, 94vw)" append-to-body :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <el-form :model="moveForm" label-width="90px" :disabled="busy">
      <el-form-item label="当前笼位">{{ cage?.room }} · {{ cage?.cage_code }}</el-form-item>
      <el-form-item label="已选小鼠">
        <div class="flex flex-wrap gap-1">
          <el-tag v-for="mouse in movingMice" :key="mouse.id" size="small" effect="plain">{{ mouse.mouse_code }}</el-tag>
        </div>
      </el-form-item>
      <el-form-item label="目标鼠房" required>
        <el-select v-model="moveForm.target_room" filterable placeholder="选择目标鼠房" style="width: 100%" @change="onMoveRoomChange">
          <el-option-group label="已有鼠房">
            <el-option v-for="room in roomOptions" :key="`cage:${room}`" :label="room" :value="`cage:${room}`" />
          </el-option-group>
          <el-option-group v-if="canHandoffMice" label="交给领取人管理">
            <el-option v-for="room in transferRoomOptions" :key="`transfer:${room}`" :label="room" :value="`transfer:${room}`" />
          </el-option-group>
        </el-select>
      </el-form-item>
      <el-form-item v-if="!isDirectHandoff" label="目标笼位" required>
        <el-select v-model="moveForm.target_cage_code" filterable allow-create default-first-option placeholder="选择已有笼位或输入新笼号" style="width: 100%">
          <el-option v-for="target in targetCages" :key="target.id" :label="`${target.cage_code}（${target.mouse_count || 0}只）`" :value="target.cage_code" />
        </el-select>
      </el-form-item>
    </el-form>
    <div class="text-xs text-gray-500">{{ isDirectHandoff ? '交给领取人管理，无需目标笼位；小鼠将移出原笼位。' : '换笼完成后会写入变动日志。' }}</div>
    <template #footer>
      <el-button :disabled="busy" @click="moving = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="submitMove">{{ isDirectHandoff ? '确认交接' : '确认换笼' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { cagesApi, miceApi, settingsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import StrainSelect from './StrainSelect.vue'
import SetOwnerDialog from './SetOwnerDialog.vue'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'
import { useArchiveDialogs } from '@/composables/useArchiveDialogs'

const props = defineProps({ modelValue: Boolean, cageId: Number })
const emit = defineEmits(['update:modelValue', 'refresh'])
const archiveDialogs = useArchiveDialogs()
const authStore = useAuthStore()
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const cage = ref(null)
const loading = ref(false)
const busy = ref(false)
const adding = ref(false)
const selectedMice = ref([])
const settingOwner = ref(false)
const ownerMice = ref([])
const editingBatch = ref(false)
const batchEditForm = reactive({ updateStrain: false, strain: '', updateDob: false, dob: '', updateGender: false, gender: '' })
const moving = ref(false)
const movingMice = ref([])
const moveForm = reactive({ target_room: '', target_cage_code: '' })
const roomOptions = ref([])
const transferRoomOptions = ref([])
const targetCages = ref([])
const canHandoffMice = computed(() => movingMice.value.length > 0 && movingMice.value.every(mouse => mouse.owner_name?.trim()))
const isDirectHandoff = computed(() => moveForm.target_room.startsWith('transfer:'))
const selectedMoveRoom = computed(() => moveForm.target_room.slice(moveForm.target_room.indexOf(':') + 1))
const form = reactive({ add_count: 1, start_code: '', mouse_code: '', strain: '', gender: '未知', dob: '', notes: '' })
let requestId = 0
let targetCageRequestId = 0

async function loadCage() {
  const id = ++requestId
  cage.value = null
  selectedMice.value = []
  loading.value = true
  try {
    const result = await cagesApi.getCage(props.cageId)
    if (id === requestId) cage.value = result
  } catch (e) {
    if (id === requestId) ElMessage.error(e.response?.data?.detail || '加载笼位失败')
  } finally {
    if (id === requestId) loading.value = false
  }
}

watch(() => [props.modelValue, props.cageId], ([open, id]) => {
  settingOwner.value = false
  if (open && id) { adding.value = false; loadCage() }
  else { adding.value = false; editingBatch.value = false; moving.value = false; requestId++; loading.value = false }
}, { immediate: true })

function handleSelectionChange(selection) {
  selectedMice.value = selection
}

function openSetOwner() {
  if (busy.value || !selectedMice.value.length || !authStore.isAdmin) return
  ownerMice.value = [...selectedMice.value]
  settingOwner.value = true
}

function openMouse(mouse) {
  archiveDialogs.openMouse(mouse, refreshCage)
}

function editCage() {
  if (!cage.value?.id || !authStore.isAdmin || busy.value) return
  archiveDialogs.openCageEditor(cage.value.id, refreshCage)
}

async function refreshCage() {
  emit('refresh')
  window.dispatchEvent(new Event('todos-updated'))
  await loadCage()
}

function openBatchEdit() {
  if (!selectedMice.value.length || !authStore.isAdmin) return
  const mice = selectedMice.value
  const first = mice[0]
  Object.assign(batchEditForm, {
    updateStrain: false,
    strain: mice.every(mouse => (mouse.strain || '') === (first.strain || '')) ? (first.strain || '') : '',
    updateDob: false,
    dob: mice.every(mouse => (mouse.dob || '') === (first.dob || '')) ? (first.dob || '') : '',
    updateGender: false,
    gender: mice.every(mouse => (mouse.gender || '') === (first.gender || '')) ? (first.gender || '') : ''
  })
  editingBatch.value = true
}

async function submitBatchEdit() {
  if (busy.value || !selectedMice.value.length || !authStore.isAdmin) return
  if (!batchEditForm.updateStrain && !batchEditForm.updateDob && !batchEditForm.updateGender) return ElMessage.warning('请至少勾选一个要修改的字段')
  if (batchEditForm.updateGender && !batchEditForm.gender) return ElMessage.warning('请选择性别')
  const payload = { mouse_ids: selectedMice.value.map(mouse => mouse.id) }
  if (batchEditForm.updateStrain) payload.strain = (batchEditForm.strain || '').trim()
  if (batchEditForm.updateDob) payload.dob = batchEditForm.dob || null
  if (batchEditForm.updateGender) payload.gender = batchEditForm.gender
  busy.value = true
  try {
    const result = await miceApi.batchUpdateFields(payload)
    editingBatch.value = false
    ElMessage.success(result.message || '批量编辑成功')
    await refreshCage()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '批量编辑失败') }
  finally { busy.value = false }
}

async function loadTargetCages(room) {
  const id = ++targetCageRequestId
  targetCages.value = []
  if (!room) return
  try {
    const cages = await cagesApi.listCages({ room })
    if (id === targetCageRequestId) targetCages.value = cages
  } catch (e) {
    if (id === targetCageRequestId) ElMessage.error(e.response?.data?.detail || '加载目标笼位失败')
  }
}

async function openMove(mice) {
  if (!cage.value || !mice.length || !authStore.isAdmin || busy.value) return
  movingMice.value = [...mice]
  Object.assign(moveForm, { target_room: `cage:${cage.value.room}`, target_cage_code: '' })
  roomOptions.value = []
  transferRoomOptions.value = []
  loadTargetCages(cage.value.room)
  moving.value = true
  try {
    roomOptions.value = await cagesApi.listRooms()
    if (canHandoffMice.value) {
      const settings = await settingsApi.getPublic()
      transferRoomOptions.value = (settings.transfer_rooms || []).filter(room => room !== '东四')
    }
  } catch (e) { ElMessage.error(e.response?.data?.detail || '加载鼠房选项失败') }
}

function onMoveRoomChange() {
  moveForm.target_cage_code = ''
  loadTargetCages(isDirectHandoff.value ? '' : selectedMoveRoom.value)
}

async function submitMove() {
  if (busy.value || !movingMice.value.length || !cage.value || !authStore.isAdmin) return
  const room = selectedMoveRoom.value.trim()
  const cageCode = moveForm.target_cage_code.trim()
  if (!room || (!isDirectHandoff.value && !cageCode)) return ElMessage.warning('请选择目标鼠房和笼位')
  if (isDirectHandoff.value && !canHandoffMice.value) return ElMessage.warning('请先为全部选中小鼠设置领取人')
  if (!isDirectHandoff.value && room === cage.value.room && cageCode === cage.value.cage_code) return ElMessage.warning('目标笼位不能与当前笼位相同')
  busy.value = true
  try {
    const result = await miceApi.batchTransfer({
      mouse_ids: movingMice.value.map(mouse => mouse.id),
      target_room: room,
      target_cage_code: isDirectHandoff.value ? undefined : cageCode,
      handoff_to_owner: isDirectHandoff.value
    })
    moving.value = false
    ElMessage.success(result.message || '换笼成功')
    await refreshCage()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '换笼失败') }
  finally { busy.value = false }
}

function openAdd() {
  Object.assign(form, { add_count: 1, start_code: '', mouse_code: '', strain: cage.value.strain || '', gender: ['M', 'F'].includes(cage.value.gender) ? cage.value.gender : '未知', dob: '', notes: '' })
  adding.value = true
}

function updateMouseCodes() {
  form.mouse_code = generateSequentialMouseCodes(form.start_code, form.add_count).join(', ')
}

async function addMouse() {
  if (busy.value || !cage.value || !authStore.isAdmin) return
  const codes = [...new Set(form.mouse_code.split(/[,，\s]+/).filter(Boolean))]
  if (!codes.length) return ElMessage.warning('请输入小鼠编号')
  busy.value = true
  try {
    const { add_count, start_code, mouse_code, ...sharedFields } = form
    const result = await miceApi.batchCreateMice({ ...sharedFields, mouse_codes: codes, dob: form.dob || null, cage_code: cage.value.cage_code, source_room: cage.value.room, status: '在笼' })
    adding.value = false
    if (result.skipped_codes.length) ElMessage.warning(result.message)
    else ElMessage.success(result.message)
    await refreshCage()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '新增小鼠失败') }
  finally { busy.value = false }
}

async function removeMouse(mouse) {
  if (busy.value || !cage.value || !authStore.isAdmin) return
  busy.value = true
  try {
    await miceApi.batchUpdateStatus({ mouse_ids: [mouse.id], status: '出笼' })
    ElMessage.success('已移除鼠：笼位关联已清除，小鼠档案已保留')
    await refreshCage()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '移出笼位失败') }
  finally { busy.value = false }
}
</script>
