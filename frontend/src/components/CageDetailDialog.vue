<template>
  <el-dialog v-model="visible" title="查看笼位" width="min(720px, 94vw)" append-to-body :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <div v-loading="loading">
      <template v-if="cage">
        <div class="mb-3 font-semibold">{{ cage.room }} · {{ cage.cage_code }} · {{ cage.strain || '未指定品系' }}（{{ cage.mice.length }} 只）</div>
        <div class="text-xs text-gray-500 mb-3">移出笼位仅解除笼位关联，保留小鼠档案、领取人及记录。操作立即生效。</div>
        <el-table :data="cage.mice" max-height="300" empty-text="当前为空笼">
          <el-table-column prop="mouse_code" label="编号" min-width="100" />
          <el-table-column prop="strain" label="品系" min-width="100" />
          <el-table-column prop="gender" label="性别" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.gender === 'M'" size="small" type="primary" effect="light">♂ 雄</el-tag>
              <el-tag v-else-if="row.gender === 'F'" size="small" type="danger" effect="light">♀ 雌</el-tag>
              <el-tag v-else size="small" type="info">未知</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="owner_name" label="领取人" min-width="90" />
          <el-table-column v-if="authStore.isAdmin" label="操作" width="100">
            <template #default="{ row }">
              <el-popconfirm :title="`将 ${row.mouse_code} 移出本笼？只清除笼位，小鼠档案将完整保留。`" @confirm="removeMouse(row)">
                <template #reference><el-button type="warning" link :disabled="busy">移除鼠</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        <template v-if="authStore.isAdmin">
          <el-button class="mt-3" type="primary" :disabled="busy" @click="openAdd">新增鼠</el-button>
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
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { cagesApi, miceApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import StrainSelect from './StrainSelect.vue'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'

const props = defineProps({ modelValue: Boolean, cageId: Number })
const emit = defineEmits(['update:modelValue', 'refresh'])
const authStore = useAuthStore()
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const cage = ref(null)
const loading = ref(false)
const busy = ref(false)
const adding = ref(false)
const form = reactive({ add_count: 1, start_code: '', mouse_code: '', strain: '', gender: '未知', dob: '', notes: '' })
let requestId = 0

async function loadCage() {
  const id = ++requestId
  cage.value = null
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
  if (open && id) { adding.value = false; loadCage() }
  else { adding.value = false; requestId++; loading.value = false }
}, { immediate: true })

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
    emit('refresh')
    if (result.skipped_codes.length) ElMessage.warning(result.message)
    else ElMessage.success(result.message)
    await loadCage()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '新增小鼠失败') }
  finally { busy.value = false }
}

async function removeMouse(mouse) {
  if (busy.value || !cage.value || !authStore.isAdmin) return
  busy.value = true
  try {
    await miceApi.batchUpdateStatus({ mouse_ids: [mouse.id], status: '出笼' })
    cage.value.mice = cage.value.mice.filter(item => item.id !== mouse.id)
    emit('refresh')
    ElMessage.success('已移除鼠：笼位关联已清除，小鼠档案已保留')
  } catch (e) { ElMessage.error(e.response?.data?.detail || '移出笼位失败') }
  finally { busy.value = false }
}
</script>
