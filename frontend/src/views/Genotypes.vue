<template>
  <div class="genotypes-page">
    <div class="genotype-toolbar bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">小鼠基因型鉴定结果档案</div>
        <div class="text-xs text-gray-500 mt-1">
          记录实验室各批次小鼠 PCR 基因鉴定结果、父母系谱配对及等位基因型分析
        </div>
      </div>

      <div class="genotype-filters flex items-center gap-3">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索耳标、品系、父母系谱"
          clearable
          prefix-icon="Search"
          style="width: 240px"
          @keyup.enter="loadGenotypes"
        />

        <el-input
          v-model="filters.genotype_1"
          placeholder="按鉴定结果筛选 (如 阳性, HET)"
          clearable
          style="width: 200px"
          @keyup.enter="loadGenotypes"
        />

        <el-button type="primary" @click="loadGenotypes">查询</el-button>

        <el-button v-if="authStore.isAdmin" type="success" plain @click="openAddDialog">
          <el-icon class="mr-1"><Plus /></el-icon> 录入鉴定结果
        </el-button>
      </div>
    </div>

    <!-- Genotype Table -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table v-loading="loading" :data="genotypes" stripe style="width: 100%">
        <el-table-column prop="test_date" label="测试日期" width="110">
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-600">{{ row.test_date || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="mouse_code" label="耳标编号 (点击查档案)" width="150" fixed>
          <template #default="{ row }">
            <div
              class="inline-flex items-center gap-1.5 cursor-pointer text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded transition-colors group"
              title="点击查看小鼠详细档案、父母系谱及流转记录"
              @click="openMouseDetail(row)"
            >
              <span class="font-bold font-mono text-sm underline-offset-2 group-hover:underline">
                {{ row.mouse_code }}
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="strain" label="品系" min-width="120">
          <template #default="{ row }">
            <span class="font-semibold text-blue-700">{{ row.strain || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="gender" label="性别" width="70">
          <template #default="{ row }">
            <span v-if="row.gender === 'M'" class="text-blue-500 font-bold">♂ 雄</span>
            <span v-else-if="row.gender === 'F'" class="text-pink-500 font-bold">♀ 雌</span>
            <span v-else class="text-gray-400 text-xs">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="dob" label="出生日期" width="110">
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-600">{{ row.dob || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="parents" label="父母系谱 (M+F)" min-width="190">
          <template #default="{ row }">
            <PedigreeTags :parents="row.parents" @click-parent="openMouseDetail" />
          </template>
        </el-table-column>

        <el-table-column prop="genotype_1" label="Genotype 1" width="130">
          <template #default="{ row }">
            <el-tag
              v-if="row.genotype_1"
              size="small"
              :type="row.genotype_1.includes('阳') || row.genotype_1.includes('纯') || row.genotype_1.includes('HET') ? 'success' : 'info'"
            >
              {{ row.genotype_1 }}
            </el-tag>
            <span v-else class="text-gray-300 text-xs">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="genotype_2" label="Genotype 2" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.genotype_2" size="small" type="warning">{{ row.genotype_2 }}</el-tag>
            <span v-else class="text-gray-300 text-xs">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="genotype_3" label="Genotype 3" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.genotype_3" size="small" type="info">{{ row.genotype_3 }}</el-tag>
            <span v-else class="text-gray-300 text-xs">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="op_record" label="操作记录/人员" width="120">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.op_record || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="notes" label="备注" min-width="140">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.notes || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column v-if="authStore.isAdmin" label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="info" link @click="openEditDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除该条鉴定记录吗？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="p-3 border-t border-gray-100 flex items-center justify-between">
        <div class="text-xs text-gray-500">
          共 <span class="font-bold text-gray-800">{{ total }}</span> 条基因鉴定记录
        </div>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadGenotypes"
          @current-change="loadGenotypes"
        />
      </div>
    </div>

    <!-- Add/Edit Genotype Dialog -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑基因鉴定结果' : '录入小鼠基因鉴定'" width="540px" align-center>
      <el-form :model="form" label-width="110px" class="genotype-form" :disabled="saving">
        <template v-if="!isEdit">
          <el-form-item label="新增数量" required>
            <el-input-number v-model="addCount" :min="1" :max="500" @change="updateGeneratedMouseCodes" />
          </el-form-item>
          <el-form-item label="起始编号" required>
            <el-input v-model="startCode" placeholder="如 B592" @input="updateGeneratedMouseCodes" />
            <div class="text-xs text-gray-500 mt-1">编号末尾需包含数字；例如 B592、新增 3 只，将生成 B592 至 B594。</div>
          </el-form-item>
          <el-form-item label="编号列表" required>
            <el-input
              v-model="form.mouse_code"
              type="textarea"
              :rows="3"
              placeholder="自动生成后仍可手动调整，多个编号用中英文逗号、顿号或换行分隔"
            />
            <div class="text-xs text-gray-500 mt-1">{{ lookupLoading ? '正在查询小鼠档案…' : '每个编号分别建立鉴定记录；品系、系谱留空时沿用各自档案。' }}</div>
          </el-form-item>
        </template>
        <el-form-item v-else label="耳标编号" required>
          <el-input v-model="form.mouse_code" disabled />
        </el-form-item>
        <el-form-item label="测试日期">
          <el-date-picker v-model="form.test_date" type="date" value-format="YYYY-MM-DD" placeholder="选择测试日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="品系">
          <el-select v-model="form.strain" filterable allow-create default-first-option clearable placeholder="选择品系或输入自定义品系" style="width: 100%" @change="manualFields.add('strain')">
            <el-option v-for="strain in strainOptions" :key="strain" :label="strain" :value="strain" />
          </el-select>
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="form.gender" @change="manualFields.add('gender')">
            <el-radio value="">沿用档案</el-radio>
            <el-radio value="M">雄 (M)</el-radio>
            <el-radio value="F">雌 (F)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="父母系谱">
          <el-input v-model="form.parents" placeholder="如 E925M+E822F、E824F" @input="manualFields.add('parents')" />
        </el-form-item>
        <el-form-item label="Genotype 1">
          <el-input v-model="form.genotype_1" placeholder="如 阳性, 野生型, 杂合子, 纯合子, HET" />
        </el-form-item>
        <el-form-item label="Genotype 2">
          <el-input v-model="form.genotype_2" placeholder="第二基因型结果 (选填)" />
        </el-form-item>
        <el-form-item label="Genotype 3">
          <el-input v-model="form.genotype_3" placeholder="第三基因型结果 (选填)" />
        </el-form-item>
        <el-form-item label="操作人/记录">
          <el-input v-model="form.op_record" placeholder="操作人员简记" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="lookupLoading" @click="submitForm">保存记录</el-button>
      </template>
    </el-dialog>

    <!-- Mouse Detail Modal -->
    <MouseDetailModal
      v-model="showMouseDetailModal"
      :mouse-code="selectedMouseCode"
      :mouse-id="selectedMouseId"
      @refresh="loadGenotypes"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { genotypesApi, miceApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import PedigreeTags from '@/components/PedigreeTags.vue'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const loading = ref(false)
const genotypes = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const filters = reactive({
  keyword: '',
  genotype_1: ''
})

const showDialog = ref(false)
const isEdit = ref(false)
const currentEditId = ref(null)
const saving = ref(false)
const lookupLoading = ref(false)
const strainOptions = ref([])
const addCount = ref(1)
const startCode = ref('')
const manualFields = new Set()
const form = reactive({
  mouse_code: '',
  test_date: '',
  strain: '',
  gender: '',
  parents: '',
  genotype_1: '',
  genotype_2: '',
  genotype_3: '',
  op_record: '',
  notes: ''
})

function parseCodes(value) {
  return [...new Set(value.split(/[,，、\n]+/).map(code => code.trim()).filter(Boolean))]
}

function updateGeneratedMouseCodes() {
  form.mouse_code = generateSequentialMouseCodes(startCode.value, addCount.value).join(', ')
}

watch(() => [form.mouse_code, showDialog.value], ([value, visible], _, onCleanup) => {
  lookupLoading.value = false
  if (!visible || isEdit.value) return
  for (const field of ['strain', 'parents', 'gender']) {
    if (!manualFields.has(field)) form[field] = ''
  }
  const codes = parseCodes(value)
  if (!codes.length || codes.length > 500) return
  let cancelled = false
  lookupLoading.value = true
  const timer = setTimeout(async () => {
    try {
      const mice = await Promise.all(codes.map(async code => {
        try {
          const mouse = await miceApi.getMouseByCode(code)
          // The existing lookup endpoint also returns partial matches.
          return mouse.mouse_code === code
            ? { ...mouse, gender: ['M', 'F'].includes(mouse.gender) ? mouse.gender : '' }
            : null
        } catch (error) {
          if (error.response?.status === 404) return null
          throw error
        }
      }))
      if (cancelled) return
      for (const field of ['strain', 'parents', 'gender']) {
        const values = mice.map(mouse => mouse?.[field] || '')
        if (!manualFields.has(field)) {
          form[field] = values.every(value => value === values[0]) ? values[0] : ''
        }
      }
    } catch {
      if (!cancelled) ElMessage.warning('小鼠档案查询失败，可手动填写或重新输入耳标重试')
    } finally {
      if (!cancelled) lookupLoading.value = false
    }
  }, 300)
  onCleanup(() => { cancelled = true; clearTimeout(timer) })
})

// Mouse detail modal
const showMouseDetailModal = ref(false)
const selectedMouseCode = ref('')
const selectedMouseId = ref(null)

function openMouseDetail(rowOrCode) {
  if (typeof rowOrCode === 'string') {
    selectedMouseCode.value = rowOrCode
    selectedMouseId.value = null
  } else {
    selectedMouseCode.value = rowOrCode?.mouse_code || ''
    selectedMouseId.value = rowOrCode?.mouse_id || null
  }
  showMouseDetailModal.value = true
}

async function loadGenotypes() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      genotype_1: filters.genotype_1 || undefined
    }
    const res = await genotypesApi.listGenotypes(params)
    if (res && res.items) {
      genotypes.value = res.items
      total.value = res.total
    } else if (Array.isArray(res)) {
      genotypes.value = res
      total.value = res.length
    }
  } catch (e) {
    ElMessage.error('加载基因鉴定记录失败')
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  manualFields.clear()
  isEdit.value = false
  currentEditId.value = null
  addCount.value = 1
  startCode.value = ''
  Object.assign(form, {
    mouse_code: '',
    test_date: new Date().toISOString().split('T')[0],
    strain: '',
    gender: '',
    parents: '',
    genotype_1: '',
    genotype_2: '',
    genotype_3: '',
    op_record: '',
    notes: ''
  })
  showDialog.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  currentEditId.value = row.id
  Object.assign(form, {
    mouse_code: row.mouse_code,
    test_date: row.test_date || '',
    strain: row.strain || '',
    gender: row.gender || 'M',
    parents: row.parents || '',
    genotype_1: row.genotype_1 || '',
    genotype_2: row.genotype_2 || '',
    genotype_3: row.genotype_3 || '',
    op_record: row.op_record || '',
    notes: row.notes || ''
  })
  showDialog.value = true
}

async function submitForm() {
  if (saving.value || lookupLoading.value) return
  const codes = parseCodes(form.mouse_code)
  if (!codes.length) {
    ElMessage.warning('请输入耳标编号')
    return
  }
  if (codes.length > 500) {
    ElMessage.warning('每次最多录入 500 个耳标编号')
    return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await genotypesApi.updateGenotype(currentEditId.value, form)
      ElMessage.success('鉴定记录已更新')
    } else {
      await genotypesApi.createGenotypes(codes.map(mouse_code => ({ ...form, mouse_code })))
      ElMessage.success(`已录入 ${codes.length} 条鉴定记录`)
    }
    showDialog.value = false
    loadGenotypes()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await genotypesApi.deleteGenotype(id)
    ElMessage.success('删除成功')
    loadGenotypes()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadGenotypes()
  miceApi.getAllStrains().then(strains => { strainOptions.value = strains }).catch(() => {
    ElMessage.warning('品系列表加载失败，仍可自定义输入')
  })
})
</script>

<style scoped>
.genotype-form :deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
