<template>
  <div class="genotypes-page">
    <div class="genotype-toolbar bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">小鼠基因型鉴定结果档案</div>
        <div class="text-xs text-gray-500 mt-1">
          先登记待检验小鼠，再填写结果；支持批量编号和向下填充基因型
        </div>
      </div>

      <div class="genotype-filters flex items-center gap-3">
        <el-select v-model="filters.sort" style="width: 185px" aria-label="鉴定记录排序" @change="searchGenotypes">
          <el-option v-for="option in genotypeSortOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-select v-model="filters.test_status" placeholder="全部鉴定状态" clearable style="width: 150px" @change="searchGenotypes">
          <el-option label="待检验" value="pending" />
          <el-option label="已有结果" value="tested" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="搜索耳标、品系、父母系谱"
          clearable
          prefix-icon="Search"
          style="width: 240px"
          @keyup.enter="searchGenotypes"
          @clear="searchGenotypes"
        />

        <el-button type="primary" @click="searchGenotypes">查询</el-button>

        <el-button v-if="authStore.isAdmin" type="primary" plain @click="openAddDialog(true)">
          <el-icon class="mr-1"><Plus /></el-icon> 登记待检验小鼠
        </el-button>
        <el-button v-if="authStore.isAdmin" type="success" plain @click="openAddDialog(false)">
          <el-icon class="mr-1"><Plus /></el-icon> 录入鉴定结果
        </el-button>
      </div>
    </div>

    <!-- Genotype Table -->
    <div v-if="authStore.isAdmin" class="text-xs text-gray-500 mb-2" role="status">
      {{ gridSaving ? '正在保存基因型…' : fillDrag ? `松开鼠标，将填充 ${Math.abs(fillDrag.endIndex - fillDrag.startIndex)} 条记录` : '双击 Genotype 单元格填写或选择结果，再拖动右下角蓝色方块向下填充，覆盖该列原值并自动保存。填充限当前页；编辑时保持行位置，查询或翻页后刷新筛选。' }}
    </div>
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table v-loading="loading || gridSaving" :data="genotypes" row-key="id" stripe style="width: 100%">
        <el-table-column label="鉴定状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="hasGenotypeResult(row) ? 'success' : 'warning'">{{ hasGenotypeResult(row) ? '已有结果' : '待检验' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dob" label="出生日期" width="110">
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-600">{{ row.dob || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="test_date" label="鉴定日期" width="110">
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

        <el-table-column prop="parents" label="父母系谱 (M+F)" min-width="190">
          <template #default="{ row }">
            <PedigreeTags :parents="row.parents" @click-parent="openMouseDetail" />
          </template>
        </el-table-column>

        <el-table-column v-for="(field, index) in genotypeFields" :key="field" :prop="field" :label="`Genotype ${index + 1}`" width="175">
          <template #header>
            <GenotypeFilterHeader
              :label="`Genotype ${index + 1}`"
              :model-value="filters[field]"
              :options="existingGenotypeOptions[field]"
              :loading="optionsLoading"
              @update:model-value="values => updateGenotypeFilter(field, values)"
            />
          </template>
          <template #default="{ row, $index }">
            <GenotypeGridCell
              :value="row[field] || ''"
              :options="existingGenotypeOptions[field]"
              :tag-type="index === 1 ? 'warning' : index === 2 ? 'info' : /阳|纯|HET/.test(row[field] || '') ? 'success' : 'info'"
              :editable="authStore.isAdmin"
              :disabled="gridSaving || loading || !!fillDrag"
              :active="activeCell?.id === row.id && activeCell?.field === field"
              :in-fill-range="isInFillRange(field, $index)"
              @activate="activateCell(row.id, field)"
              @save="value => saveGridValues([row.id], field, value)"
              @fill-start="event => startFill(field, $index, event)"
              @fill-enter="extendFill(field, $index)"
            />
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
            <el-button size="small" type="info" link @click="openEditDialog(row)">{{ hasGenotypeResult(row) ? '编辑' : '填写结果' }}</el-button>
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
          @size-change="page = 1"
        />
      </div>
    </div>

    <!-- Add/Edit Genotype Dialog -->
    <el-dialog v-model="showDialog" class="genotype-entry-dialog" :title="isEdit ? '编辑基因鉴定记录' : registeringPending ? '登记待检验小鼠' : '录入小鼠基因鉴定'" width="540px" align-center>
      <div v-if="registeringPending && !isEdit" class="text-xs text-gray-500 mb-4">填写编号和基本信息即可保存，基因型和鉴定日期可留空；检验后可在表格填写结果并向下填充。</div>
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
        <el-form-item v-if="isEdit || !isBatchEntry" label="出生日期">
          <el-date-picker v-model="form.dob" type="date" value-format="YYYY-MM-DD" placeholder="选择小鼠出生日期" style="width: 100%" @change="manualFields.add('dob')" />
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
        <el-form-item label="鉴定日期">
          <el-date-picker v-model="form.test_date" type="date" value-format="YYYY-MM-DD" placeholder="选择鉴定日期" style="width: 100%" />
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
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { genotypesApi, miceApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import PedigreeTags from '@/components/PedigreeTags.vue'
import GenotypeFilterHeader from '@/components/GenotypeFilterHeader.vue'
import GenotypeGridCell from '@/components/GenotypeGridCell.vue'
import { hasGenotypeResult } from '@/utils/mouseDisplay'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const loading = ref(false)
const genotypes = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const optionsLoading = ref(false)
const genotypeOptions = reactive({ genotype_1: [], genotype_2: [], genotype_3: [] })
const genotypeFields = ['genotype_1', 'genotype_2', 'genotype_3']
const genotypeSortOptions = [
  { value: 'added_desc', label: '添加顺序：倒序', sortBy: 'added', sortOrder: 'desc' },
  { value: 'added_asc', label: '添加顺序：正序', sortBy: 'added', sortOrder: 'asc' },
  { value: 'test_date_desc', label: '鉴定日期：从新到旧', sortBy: 'test_date', sortOrder: 'desc' },
  { value: 'test_date_asc', label: '鉴定日期：从旧到新', sortBy: 'test_date', sortOrder: 'asc' }
]
const savedSort = localStorage.getItem('genotype_sort')
const gridSaving = ref(false)
const activeCell = ref(null)
const fillDrag = ref(null)
const registeringPending = ref(false)
let loadRequestId = 0

const filters = reactive({
  keyword: '',
  test_status: '',
  sort: genotypeSortOptions.some(option => option.value === savedSort) ? savedSort : 'added_desc',
  genotype_1: [],
  genotype_2: [],
  genotype_3: []
})
const selectedSort = computed(() => genotypeSortOptions.find(option => option.value === filters.sort))
watch(() => filters.sort, value => localStorage.setItem('genotype_sort', value))

// Show values already visible in the table while the full option list loads.
const existingGenotypeOptions = computed(() => Object.fromEntries(
  ['genotype_1', 'genotype_2', 'genotype_3'].map(field => [field, [...new Set([
    ...genotypeOptions[field],
    ...genotypes.value.map(record => (record[field] || '').trim()),
    ...filters[field]
  ])].sort((a, b) => a.localeCompare(b, 'zh-CN'))])
))

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
  dob: '',
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

const isBatchEntry = computed(() => (
  !isEdit.value && (addCount.value > 1 || parseCodes(form.mouse_code).length > 1)
))

watch(isBatchEntry, (batch) => {
  if (batch) {
    form.dob = ''
    manualFields.delete('dob')
  }
})

function updateGeneratedMouseCodes() {
  form.mouse_code = generateSequentialMouseCodes(startCode.value, addCount.value).join(', ')
}

watch(() => [form.mouse_code, showDialog.value], ([value, visible], _, onCleanup) => {
  lookupLoading.value = false
  if (!visible || isEdit.value) return
  for (const field of ['strain', 'parents', 'gender', 'dob']) {
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
      const lookupFields = codes.length > 1
        ? ['strain', 'parents', 'gender']
        : ['strain', 'parents', 'gender', 'dob']
      for (const field of lookupFields) {
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

function searchGenotypes() {
  if (page.value === 1) loadGenotypes()
  else page.value = 1
}

function updateGenotypeFilter(field, values) {
  filters[field] = values
  searchGenotypes()
}

watch([page, pageSize], loadGenotypes)

async function loadGenotypeOptions() {
  optionsLoading.value = true
  try {
    Object.assign(genotypeOptions, await genotypesApi.getFilterOptions())
  } catch {
    ElMessage.warning('鉴定结果筛选选项加载失败')
  } finally {
    optionsLoading.value = false
  }
}

async function loadGenotypes() {
  cancelFill()
  const requestId = ++loadRequestId
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      test_status: filters.test_status || undefined,
      sort_by: selectedSort.value.sortBy,
      sort_order: selectedSort.value.sortOrder,
      genotype_1_values: filters.genotype_1.length ? filters.genotype_1 : undefined,
      genotype_2_values: filters.genotype_2.length ? filters.genotype_2 : undefined,
      genotype_3_values: filters.genotype_3.length ? filters.genotype_3 : undefined
    }
    const res = await genotypesApi.listGenotypes(params)
    if (requestId !== loadRequestId) return
    if (res && res.items) {
      genotypes.value = res.items
      total.value = res.total
    } else if (Array.isArray(res)) {
      genotypes.value = res
      total.value = res.length
    }
  } catch (e) {
    if (requestId === loadRequestId) ElMessage.error('加载基因鉴定记录失败')
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

function activateCell(id, field) {
  if (!gridSaving.value && !fillDrag.value) activeCell.value = { id, field }
}

async function saveGridValues(recordIds, field, value) {
  if (gridSaving.value || loading.value || !authStore.isAdmin) return
  gridSaving.value = true
  try {
    const result = await genotypesApi.fillGenotypes({ record_ids: recordIds, field, value })
    // Keep the source and surrounding rows stable for the next fill gesture.
    const updates = new Map(result.items.map(record => [record.id, record]))
    for (const row of genotypes.value) {
      if (updates.has(row.id)) Object.assign(row, updates.get(row.id))
    }
    ElMessage.success(`已保存 ${result.updated} 条基因型`)
    await loadGenotypeOptions()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '基因型保存失败，请重试')
  } finally {
    gridSaving.value = false
  }
}

function startFill(field, rowIndex, event) {
  if (event.button !== 0 || gridSaving.value || loading.value || !authStore.isAdmin) return
  cancelFill()
  const row = genotypes.value[rowIndex]
  activeCell.value = { id: row.id, field }
  fillDrag.value = {
    field, startIndex: rowIndex, endIndex: rowIndex, value: row[field] || '',
    previousUserSelect: document.body.style.userSelect
  }
  document.body.style.userSelect = 'none'
  document.addEventListener('pointerup', finishFill)
  document.addEventListener('pointercancel', cancelFill)
  document.addEventListener('keydown', handleFillKeydown)
}

function extendFill(field, rowIndex) {
  if (fillDrag.value?.field === field) fillDrag.value.endIndex = rowIndex
}

function isInFillRange(field, rowIndex) {
  const drag = fillDrag.value
  return drag?.field === field && rowIndex >= Math.min(drag.startIndex, drag.endIndex)
    && rowIndex <= Math.max(drag.startIndex, drag.endIndex)
}

function finishFill() {
  const drag = fillDrag.value
  if (!drag) return
  const ids = genotypes.value
    .slice(Math.min(drag.startIndex, drag.endIndex), Math.max(drag.startIndex, drag.endIndex) + 1)
    .filter(row => row.id !== activeCell.value?.id)
    .map(row => row.id)
  cancelFill()
  if (ids.length) saveGridValues(ids, drag.field, drag.value)
}

function handleFillKeydown(event) {
  if (event.key === 'Escape') cancelFill()
}

function cancelFill() {
  if (fillDrag.value) document.body.style.userSelect = fillDrag.value.previousUserSelect
  fillDrag.value = null
  document.removeEventListener('pointerup', finishFill)
  document.removeEventListener('pointercancel', cancelFill)
  document.removeEventListener('keydown', handleFillKeydown)
}

onBeforeUnmount(cancelFill)

function openAddDialog(pending = false) {
  registeringPending.value = pending
  manualFields.clear()
  isEdit.value = false
  currentEditId.value = null
  addCount.value = 1
  startCode.value = ''
  Object.assign(form, {
    mouse_code: '',
    test_date: pending ? '' : new Date().toLocaleDateString('sv-SE'),
    dob: '',
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
  registeringPending.value = false
  isEdit.value = true
  currentEditId.value = row.id
  Object.assign(form, {
    mouse_code: row.mouse_code,
    test_date: row.test_date || '',
    dob: row.dob || '',
    strain: row.strain || '',
    gender: row.gender || '',
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
    loadGenotypeOptions()
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
    loadGenotypeOptions()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadGenotypes()
  loadGenotypeOptions()
  miceApi.getAllStrains().then(strains => { strainOptions.value = strains }).catch(() => {
    ElMessage.warning('品系列表加载失败，仍可自定义输入')
  })
})
</script>

<style scoped>
:global(.genotype-entry-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}
:global(.genotype-entry-dialog .el-dialog__header),
:global(.genotype-entry-dialog .el-dialog__footer) {
  flex-shrink: 0;
}
:global(.genotype-entry-dialog .el-dialog__body) {
  min-height: 0;
  overflow-y: auto;
}
.genotype-toolbar, .genotype-filters { flex-wrap: wrap; gap: 12px; }
.genotype-form :deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
