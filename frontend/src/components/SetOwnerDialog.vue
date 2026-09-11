<template>
  <el-dialog
    v-model="visible"
    title="指定小鼠领取人 / 领用登记"
    width="560px"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="mb-4 text-sm text-gray-600">
      当前已选择 <span class="font-bold text-blue-600">{{ targetMice.length }}</span> 只小鼠：
      <div class="mt-1.5 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto p-2 bg-gray-50 rounded border border-gray-200">
        <el-tag
          v-for="m in targetMice"
          :key="m.id || m.mouse_code"
          size="small"
          effect="plain"
          type="info"
        >
          {{ m.mouse_code }}
          <span v-if="m.strain" class="text-xs text-gray-400 ml-1">({{ m.strain }})</span>
        </el-tag>
      </div>
    </div>

    <el-form :model="form" :rules="rules" ref="formRef" label-width="125px" size="default">
      <el-form-item label="领取人" prop="owner_name" required>
        <el-select
          v-model="form.owner_name"
          filterable
          allow-create
          default-first-option
          placeholder="请选择成员或直接输入新名字"
          style="width: 100%"
        >
          <el-option
            v-for="c in claimerOptions"
            :key="c.id"
            :label="`${c.name} (${c.role || '成员'}, 已领 ${c.mouse_count || 0} 只)`"
            :value="c.name"
          >
            <div class="flex items-center justify-between">
              <span class="flex items-center gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full inline-block shadow-2xs" :style="{ backgroundColor: c.color || '#2563eb' }"></span>
                <span class="font-bold">{{ c.name }}</span>
                <span class="text-xs text-gray-400">({{ c.role || '学生' }})</span>
              </span>
              <span class="text-xs text-gray-400">已领 {{ c.mouse_count || 0 }} 只</span>
            </div>
          </el-option>
        </el-select>
        <div class="text-xs text-gray-400 mt-1">支持下拉选择已有课题组成员，也可直接回车创建新成员</div>
      </el-form-item>

      <el-form-item label="领用日期" prop="claim_date">
        <el-date-picker
          v-model="form.claim_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="领用目的/用途">
        <el-input
          v-model="form.claim_purpose"
          placeholder="例如：双光子成像实验、行为学测试、取脑切片等"
          maxlength="100"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="状态变更">
        <el-select
          v-model="form.status"
          filterable
          allow-create
          default-first-option
          placeholder="选择或输入新状态"
          style="width: 100%"
        >
          <el-option v-for="status in statusOptions" :key="status.id" :label="status.name" :value="status.name" />
        </el-select>
        <div v-if="form.owner_name === '安乐死'" class="text-xs text-red-500 mt-1">选择安乐死后，小鼠状态固定为死亡并自动移出笼位</div>
      </el-form-item>

      <el-divider content-position="left">可选：同步转移鼠房或笼位</el-divider>

      <el-form-item label="转入鼠房">
        <el-select v-model="form.target_room" clearable placeholder="保持当前鼠房不变" style="width: 100%">
          <el-option v-for="r in roomOptions" :key="r" :label="r" :value="r" />
        </el-select>
      </el-form-item>

      <el-form-item label="目标笼号" v-if="form.target_room">
        <el-input v-model="form.target_cage_code" placeholder="如 H9, 7A，不存在将自动创建" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          确认指定 ({{ targetMice.length }} 只)
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { miceApi, claimersApi, cagesApi, mouseStatusesApi } from '@/api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: Boolean,
  mice: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = ref(false)
const loading = ref(false)
const formRef = ref(null)
const targetMice = ref([])
const claimerOptions = ref([])
const roomOptions = ref([])
const statusOptions = ref([])

const form = reactive({
  owner_name: '',
  claim_date: new Date().toISOString().split('T')[0],
  claim_purpose: '',
  status: '已领用',
  target_room: '',
  target_cage_code: ''
})

const rules = {
  owner_name: [{ required: true, message: '请输入或选择领取人', trigger: 'change' }]
}

watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (val) {
    targetMice.value = [...props.mice]
    loadOptions()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

watch(() => form.owner_name, (ownerName) => {
  if (ownerName === '安乐死') {
    form.status = '死亡'
    form.target_room = ''
    form.target_cage_code = ''
  } else if (form.status === '死亡') {
    form.status = '已领用'
  }
})

async function loadOptions() {
  try {
    const [claimers, rooms, statuses] = await Promise.all([
      claimersApi.listClaimers(),
      cagesApi.listRooms(),
      mouseStatusesApi.listStatuses()
    ])
    claimerOptions.value = claimers
    roomOptions.value = rooms
    statusOptions.value = statuses
  } catch (e) {
    console.error('Failed to load options', e)
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const mouseCodes = targetMice.value.map(m => m.mouse_code)
      const res = await miceApi.batchSetOwner({
        mouse_codes: mouseCodes,
        owner_name: form.owner_name,
        claim_date: form.claim_date,
        claim_purpose: form.claim_purpose,
        status: form.status,
        target_room: form.target_room || undefined,
        target_cage_code: form.target_cage_code || undefined
      })
      ElMessage.success(res.message || '领取人设置成功！')
      visible.value = false
      emit('success')
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '设置失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
:deep(.el-form-item__label) {
  white-space: nowrap !important;
  font-weight: 500;
}
</style>
