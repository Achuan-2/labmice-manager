<template>
  <el-dialog
    v-model="visible"
    title="小鼠状态管理"
    width="620px"
    :close-on-click-modal="false"
  >
    <div class="text-xs text-gray-500 mb-4">
      自定义状态会用于小鼠档案、列表筛选和批量状态标记。系统状态承担笼位及领用联动，不可重命名或删除。
    </div>

    <div class="flex gap-2 mb-4">
      <el-input
        v-model="newStatusName"
        maxlength="32"
        placeholder="输入新状态名称"
        @keyup.enter="createStatus"
      />
      <el-button type="primary" :loading="creating" @click="createStatus">新增状态</el-button>
    </div>

    <el-table v-loading="loading" :data="statuses" border max-height="420">
      <el-table-column label="状态名称" min-width="210">
        <template #default="{ row }">
          <el-input
            v-if="editingId === row.id"
            v-model="editingName"
            maxlength="32"
            size="small"
            @keyup.enter="saveRename(row)"
          />
          <div v-else class="flex items-center gap-2">
            <span class="font-medium">{{ row.name }}</span>
            <el-tag v-if="row.is_system" size="small" type="info" effect="plain">系统状态</el-tag>
            <el-tag v-if="row.removes_from_cage" size="small" type="danger" effect="plain">自动出笼</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="使用中的小鼠" width="125" align="center">
        <template #default="{ row }">
          <span :class="row.usage_count ? 'font-bold text-blue-600' : 'text-gray-400'">
            {{ row.usage_count }} 只
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center">
        <template #default="{ row }">
          <template v-if="editingId === row.id">
            <el-button type="primary" link size="small" @click="saveRename(row)">保存</el-button>
            <el-button link size="small" @click="cancelRename">取消</el-button>
          </template>
          <template v-else-if="!row.is_system">
            <el-button type="primary" link size="small" @click="startRename(row)">重命名</el-button>
            <el-button type="danger" link size="small" @click="requestDelete(row)">删除</el-button>
          </template>
          <span v-else class="text-xs text-gray-400">由系统维护</span>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="visible = false">完成</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="showMigrationDialog"
    title="删除状态并迁移小鼠"
    width="480px"
    append-to-body
    :close-on-click-modal="false"
  >
    <el-alert type="warning" :closable="false" show-icon class="mb-4">
      状态“{{ deletingStatus?.name }}”仍有 {{ deletingStatus?.usage_count || 0 }} 只小鼠使用。删除前必须将这些小鼠统一转移到其他状态。
    </el-alert>
    <el-form label-width="100px">
      <el-form-item label="转移到" required>
        <el-select v-model="replacementStatus" placeholder="请选择目标状态" style="width: 100%">
          <el-option
            v-for="item in replacementOptions"
            :key="item.id"
            :label="item.name"
            :value="item.name"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showMigrationDialog = false">取消</el-button>
      <el-button type="danger" :loading="deleting" @click="confirmDeleteWithMigration">迁移并删除</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { mouseStatusesApi } from '@/api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'changed'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

const statuses = ref([])
const loading = ref(false)
const creating = ref(false)
const deleting = ref(false)
const newStatusName = ref('')
const editingId = ref(null)
const editingName = ref('')
const showMigrationDialog = ref(false)
const deletingStatus = ref(null)
const replacementStatus = ref('')

const replacementOptions = computed(() =>
  statuses.value.filter(item => item.id !== deletingStatus.value?.id)
)

watch(() => props.modelValue, value => {
  if (value) loadStatuses()
})

async function loadStatuses() {
  loading.value = true
  try {
    statuses.value = await mouseStatusesApi.listStatuses()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载状态列表失败')
  } finally {
    loading.value = false
  }
}

async function createStatus() {
  const name = newStatusName.value.trim()
  if (!name) {
    ElMessage.warning('请输入状态名称')
    return
  }
  creating.value = true
  try {
    await mouseStatusesApi.createStatus({ name })
    newStatusName.value = ''
    await loadStatuses()
    emit('changed')
    ElMessage.success(`状态 [${name}] 已新增`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '新增状态失败')
  } finally {
    creating.value = false
  }
}

function startRename(row) {
  editingId.value = row.id
  editingName.value = row.name
}

function cancelRename() {
  editingId.value = null
  editingName.value = ''
}

async function saveRename(row) {
  const name = editingName.value.trim()
  if (!name) {
    ElMessage.warning('状态名称不能为空')
    return
  }
  try {
    await mouseStatusesApi.renameStatus(row.id, { name })
    cancelRename()
    await loadStatuses()
    emit('changed')
    ElMessage.success('状态已重命名，已有小鼠已同步更新')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重命名失败')
  }
}

async function requestDelete(row) {
  if (row.usage_count > 0) {
    deletingStatus.value = row
    replacementStatus.value = ''
    showMigrationDialog.value = true
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除未使用的状态“${row.name}”吗？`, '删除状态', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    const result = await mouseStatusesApi.deleteStatus(row.id)
    ElMessage.success(result.message)
    await loadStatuses()
    emit('changed')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.detail || '删除状态失败')
    }
  }
}

async function confirmDeleteWithMigration() {
  if (!replacementStatus.value) {
    ElMessage.warning('请选择小鼠要转移到的状态')
    return
  }
  deleting.value = true
  try {
    const result = await mouseStatusesApi.deleteStatus(deletingStatus.value.id, replacementStatus.value)
    showMigrationDialog.value = false
    ElMessage.success(result.message)
    await loadStatuses()
    emit('changed')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '迁移并删除失败')
  } finally {
    deleting.value = false
  }
}
</script>
