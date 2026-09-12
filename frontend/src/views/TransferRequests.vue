<template>
  <div class="transfer-requests-page">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">转鼠需求及反馈表</div>
        <div class="text-xs text-gray-500 mt-1">
          课题组成员与访客可随时在线申请领鼠，管理员统一审批分配小鼠编号并反馈处理结果
        </div>
      </div>

      <div class="flex items-center gap-3">
        <el-input
          v-model="filters.demander"
          placeholder="按需求者姓名筛选"
          clearable
          style="width: 170px"
          @keyup.enter="loadRequests"
        />

        <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 130px" @change="loadRequests">
          <el-option label="申请中" value="申请中" />
          <el-option label="进行中" value="进行中" />
          <el-option label="已转" value="已转" />
          <el-option label="取消" value="取消" />
        </el-select>

        <el-button type="primary" @click="loadRequests">查询</el-button>

        <!-- Everyone (including guest) can submit requests! -->
        <el-button type="success" class="shrink-0 whitespace-nowrap" @click="openSubmitDialog">
          <el-icon class="mr-1"><Plus /></el-icon> 提交转鼠需求申请
        </el-button>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <!-- Active Sort Hint Bar -->
      <div v-if="sortConfig.prop" class="flex items-center justify-between px-4 py-2 bg-blue-50/80 border-b border-blue-100 text-xs text-blue-900">
        <div class="flex items-center gap-2">
          <span class="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          <span>当前按 <b>{{ columnMeta[sortConfig.prop]?.label || sortConfig.prop }}</b> {{ sortConfig.order === 'asc' ? `升序 ▲ (${columnMeta[sortConfig.prop]?.ascText})` : `降序 ▼ (${columnMeta[sortConfig.prop]?.descText})` }} 排序</span>
        </div>
        <el-button size="small" link type="primary" @click="clearSort">
          恢复默认顺序
        </el-button>
      </div>

      <el-table v-loading="loading" :data="sortedRequests" stripe style="width: 100%">
        <el-table-column prop="seq" width="95" align="center">
          <template #header>
            <ExcelSortHeader
              prop="seq"
              label="序号"
              asc-text="从小到大"
              desc-text="从大到小"
              align="center"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
        </el-table-column>

        <el-table-column prop="request_date" width="135">
          <template #header>
            <ExcelSortHeader
              prop="request_date"
              label="申请日期"
              asc-text="从早到晚"
              desc-text="从晚到早"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-600">{{ row.request_date || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="demander" width="130">
          <template #header>
            <ExcelSortHeader
              prop="demander"
              label="需求者"
              asc-text="姓名升序"
              desc-text="姓名降序"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <el-tag
              size="small"
              :style="getClaimerTagStyle(row.demander)"
              class="font-medium border"
            >
              👤 {{ row.demander }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="strain" min-width="135">
          <template #header>
            <ExcelSortHeader
              prop="strain"
              label="小鼠品系"
              asc-text="品系升序"
              desc-text="品系降序"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <span class="font-semibold text-blue-700">{{ row.strain }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="age_gender_req" width="165">
          <template #header>
            <ExcelSortHeader
              prop="age_gender_req"
              label="要求年龄/性别"
              asc-text="周龄小到大"
              desc-text="周龄大到小"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <span class="text-xs text-gray-600">{{ row.age_gender_req || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="target_room" width="155">
          <template #header>
            <ExcelSortHeader
              prop="target_room"
              label="期望转入鼠房"
              asc-text="名称升序"
              desc-text="名称降序"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.target_room || '未填写' }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="cage_count" width="95" align="center">
          <template #header>
            <ExcelSortHeader
              prop="cage_count"
              label="笼位"
              asc-text="从少到多"
              desc-text="从多到少"
              align="center"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <span>{{ row.cage_count || 1 }} 笼</span>
          </template>
        </el-table-column>

        <el-table-column prop="source_room" width="125">
          <template #header>
            <ExcelSortHeader
              prop="source_room"
              label="转出鼠房"
              asc-text="名称升序"
              desc-text="名称降序"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.source_room || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="mouse_codes" label="实际分配小鼠编号" min-width="160">
          <template #default="{ row }">
            <div v-if="row.mouse_codes" class="flex flex-wrap gap-1">
              <span
                v-for="code in splitMouseCodes(row.mouse_codes)"
                :key="code"
                class="inline-flex items-center gap-1 cursor-pointer font-mono text-xs font-bold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-2 py-0.5 rounded border border-emerald-200 transition-colors group"
                title="点击查看该小鼠详细档案、父母系谱及流转记录"
                @click="openMouseDetail(code)"
              >
                <span>{{ code }}</span>
              </span>
            </div>
            <span v-else class="text-gray-400 text-xs italic">待分配</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" width="115">
          <template #header>
            <ExcelSortHeader
              prop="status"
              label="状态"
              asc-text="流转阶段"
              desc-text="逆流转阶段"
              :active-prop="sortConfig.prop"
              :active-order="sortConfig.order"
              @sort="toggleSort"
              @clear="clearSort"
            />
          </template>
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === '已转' ? 'success' : (row.status === '取消' ? 'danger' : 'warning')"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="feedback" label="反馈与备注" min-width="140">
          <template #default="{ row }">
            <span class="text-xs text-gray-600">{{ row.feedback || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="handler" label="经办人" width="100" />

        <!-- Admin Operation Column -->
        <el-table-column v-if="authStore.isAdmin" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center gap-1">
              <el-button
                size="small"
                type="primary"
                link
                @click="openProcessDialog(row)"
              >
                {{ row.status === '已转' ? '编辑' : '审批处理' }}
              </el-button>
              <el-popconfirm
                title="确定删除此需求？已分配的小鼠将撤销分配并恢复原笼位。"
                @confirm="handleDelete(row.id)"
              >
                <template #reference>
                  <el-button size="small" type="danger" link>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Submit Request Dialog (Anyone / Guests) -->
    <el-dialog v-model="showSubmitDialog" title="提交转鼠需求申请" width="540px">
      <el-form :model="submitForm" :rules="submitRules" ref="submitFormRef" label-width="125px">
        <el-form-item label="需求者姓名" prop="demander" required>
          <el-select
            v-model="submitForm.demander"
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            :loading="claimerOptionsLoading"
            placeholder="请选择课题组成员或输入新名字"
            style="width: 100%"
          >
            <el-option v-for="member in claimerOptions" :key="member.id" :label="member.name" :value="member.name" />
          </el-select>
          <div class="text-xs text-gray-400 mt-1">可下拉选择已有成员，也可输入新名字后按回车确认</div>
        </el-form-item>
        <el-form-item label="需求小鼠品系" prop="strain" required>
          <el-select
            v-model="submitForm.strain"
            filterable
            allow-create
            default-first-option
            placeholder="请选择或输入小鼠品系"
            style="width: 100%"
          >
            <el-option v-for="strain in strainOptions" :key="strain" :label="strain" :value="strain" />
          </el-select>
        </el-form-item>
        <el-form-item label="要求年龄/性别">
          <el-input v-model="submitForm.age_gender_req" placeholder="如 成年/雄鼠, 老年/无要求" />
        </el-form-item>
        <el-form-item label="期望转入鼠房">
          <div class="transfer-room-field">
            <el-select
              v-model="submitForm.target_room"
              filterable
              allow-create
              default-first-option
              placeholder="请选择或输入新鼠房"
              style="flex: 1"
            >
              <el-option v-for="room in transferRoomOptions" :key="room" :label="room" :value="room" />
            </el-select>
            <el-button v-if="authStore.isAdmin" plain @click="openTransferRoomSettings">设置</el-button>
          </div>
          <div class="text-xs text-gray-400 mt-1">下拉选择已有选项，或直接输入新鼠房后按回车确认</div>
        </el-form-item>
        <el-form-item label="申请笼位数量">
          <el-input-number v-model="submitForm.cage_count" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="申请说明/备注">
          <el-input v-model="submitForm.feedback" type="textarea" :rows="2" placeholder="实验安排或特殊要求" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSubmitDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmitRequest">提交申请</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showTransferRoomSettings" title="设置期望转入鼠房" width="min(520px, 92vw)" append-to-body>
      <div class="transfer-room-add-row">
        <el-input
          v-model="newTransferRoomName"
          maxlength="64"
          placeholder="输入新鼠房名称"
          @keyup.enter="addTransferRoomOption"
        />
        <el-button type="primary" :loading="addingTransferRoom" @click="addTransferRoomOption">新增</el-button>
      </div>
      <div class="text-xs text-gray-400 mb-3">重命名或删除只调整今后的下拉选项，不改动已有申请记录。</div>
      <div v-for="room in transferRoomOptions" :key="room" class="transfer-room-setting-row">
        <el-input v-model="transferRoomDrafts[room]" maxlength="64" />
        <el-button
          type="primary"
          link
          :loading="savingTransferRoom === room"
          :disabled="!transferRoomDrafts[room]?.trim() || transferRoomDrafts[room]?.trim() === room"
          @click="renameTransferRoomOption(room)"
        >保存</el-button>
        <el-popconfirm
          :title="`确定删除选项“${room}”吗？`"
          @confirm="deleteTransferRoomOption(room)"
        >
          <template #reference>
            <el-button type="danger" link :loading="deletingTransferRoom === room" :disabled="transferRoomOptions.length <= 1">删除</el-button>
          </template>
        </el-popconfirm>
      </div>
    </el-dialog>

    <!-- Admin Process Request Dialog -->
    <el-dialog v-model="showProcessDialog" title="审批与处理转鼠申请" width="min(960px, 94vw)">
      <el-form :model="processForm" label-width="125px">
        <div class="bg-gray-50 p-3 rounded-lg text-xs mb-4 text-gray-700">
          <div>需求者：<b>{{ currentReq?.demander }}</b> (申请品系: <b>{{ currentReq?.strain }}</b>)</div>
          <div>要求：{{ currentReq?.age_gender_req }} | 转入鼠房: {{ currentReq?.target_room }}</div>
        </div>

        <el-form-item label="审核处理状态" required>
          <el-radio-group v-model="processForm.status">
            <el-radio value="已转">已转 (审批通过)</el-radio>
            <el-radio value="进行中">进行中 (备鼠中)</el-radio>
            <el-radio value="取消">取消需求</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="小鼠品系" required>
          <el-select
            v-model="processForm.strain"
            filterable
            allow-create
            default-first-option
            placeholder="请选择或输入小鼠品系"
            style="width: 100%"
            @change="loadCandidateMice"
          >
            <el-option v-for="strain in strainOptions" :key="strain" :label="strain" :value="strain" />
          </el-select>
        </el-form-item>

        <el-form-item label="转出鼠房">
          <el-select
            v-model="processForm.source_room"
            filterable
            placeholder="请选择转出鼠房"
            style="width: 100%"
            @change="loadCandidateMice"
          >
            <el-option v-for="room in roomOptions" :key="room" :label="room" :value="room" />
          </el-select>
        </el-form-item>

        <template v-if="processForm.status === '已转'">
          <div class="candidate-panel">
            <div class="candidate-toolbar">
              <div>
                <div class="font-semibold text-gray-700">可选小鼠</div>
                <div class="text-xs text-gray-500 mt-1">
                  {{ candidateFilterHint }}
                </div>
              </div>
              <div class="candidate-filters">
                <el-select
                  v-model="candidateFilters.gender"
                  clearable
                  placeholder="性别不限"
                  style="width: 115px"
                  @change="syncCandidateSelectionFromCodes"
                >
                  <el-option label="雄鼠 (M)" value="M" />
                  <el-option label="雌鼠 (F)" value="F" />
                </el-select>
                <!-- 周龄条件筛选: 运算符 (大于/等于/小于) + 周龄数值 -->
                <el-select
                  v-model="candidateFilters.ageOperator"
                  style="width: 125px"
                  @change="syncCandidateSelectionFromCodes"
                >
                  <el-option label="大于 (>)" value=">" />
                  <el-option label="大于等于 (≥)" value=">=" />
                  <el-option label="等于 (=)" value="=" />
                  <el-option label="小于 (<)" value="<" />
                  <el-option label="小于等于 (≤)" value="<=" />
                </el-select>
                <el-input
                  v-model="candidateFilters.ageWeeks"
                  clearable
                  placeholder="周龄"
                  style="width: 150px"
                  @input="syncCandidateSelectionFromCodes"
                >
                  <template #append>周</template>
                </el-input>
                <el-input
                  v-model="candidateFilters.keyword"
                  clearable
                  placeholder="搜索编号/品系/笼位/鼠房"
                  style="width: 190px"
                  @input="syncCandidateSelectionFromCodes"
                />
                <el-button :loading="candidateLoading" @click="loadCandidateMice">刷新</el-button>
              </div>
            </div>

            <el-table
              ref="candidateTableRef"
              v-loading="candidateLoading"
              :data="candidateMice"
              row-key="id"
              size="small"
              max-height="280"
              empty-text="暂无符合当前条件且未领取的小鼠"
              @selection-change="handleCandidateSelection"
            >
              <el-table-column type="selection" width="44" />
              <el-table-column prop="mouse_code" label="小鼠编号" min-width="110">
                <template #default="{ row }">
                  <el-button type="primary" link class="font-mono" @click.stop="openMouseDetail(row.mouse_code)">
                    {{ row.mouse_code }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column prop="strain" label="品系" min-width="110" />
              <el-table-column prop="gender" label="性别" width="70">
                <template #default="{ row }">
                  <span v-if="normalizeGender(row.gender) === 'M'" class="candidate-gender candidate-gender-male" title="雄鼠" aria-label="雄鼠">♂</span>
                  <span v-else-if="normalizeGender(row.gender) === 'F'" class="candidate-gender candidate-gender-female" title="雌鼠" aria-label="雌鼠">♀</span>
                  <span v-else class="text-gray-400">{{ row.gender || '未知' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="年龄" width="90">
                <template #default="{ row }">{{ formatMouseAge(row) }}</template>
              </el-table-column>
              <el-table-column prop="cage_room" label="鼠房 / 原鼠房" min-width="105">
                <template #default="{ row }">{{ row.assignment_source_room || row.cage_room || row.source_room || '-' }}</template>
              </el-table-column>
              <el-table-column prop="cage_code" label="笼位 / 原笼位" min-width="115">
                <template #default="{ row }">{{ row.assignment_source_cage || row.cage_code || '-' }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="90" />
            </el-table>
            <div class="text-xs text-gray-500 mt-2">
              当前显示 {{ candidateMice.length }} 只，已勾选 {{ selectedCandidateCodes.length }} 只
            </div>
          </div>

          <el-form-item label="分配小鼠编号">
            <el-input
              v-model="processForm.mouse_codes"
              type="textarea"
              :rows="2"
              placeholder="可从上方勾选，也可直接输入耳标；多个编号用逗号、空格或换行分隔"
              @blur="syncCandidateSelectionFromCodes"
            />
            <div class="text-xs text-gray-400 mt-1">
              保存审批后，小鼠将归属需求者并自动出笼，档案日志保留原鼠房及笼位。取消勾选或移除编号后保存，将恢复该鼠分配前的笼位和领取信息。
            </div>
          </el-form-item>
        </template>

        <div v-if="currentReq?.status === '已转'" class="text-xs text-orange-600 mb-3">
          已分配小鼠会保留在候选列表中，不受筛选影响。清空全部编号后保存，将全部回笼并把需求改为“进行中”；改为“取消”也会全部回笼。
        </div>

        <el-form-item label="小鼠性别">
          <el-radio-group v-model="processForm.mouse_gender">
            <el-radio value="M">雄鼠 (M)</el-radio>
            <el-radio value="F">雌鼠 (F)</el-radio>
            <el-radio value="M/F">混合 (M/F)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="处理反馈意见">
          <el-input v-model="processForm.feedback" type="textarea" :rows="2" placeholder="反馈给需求者的情况" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showProcessDialog = false">取消</el-button>
        <el-button type="primary" :loading="processing" @click="submitProcess">确认处理</el-button>
      </template>
    </el-dialog>

    <!-- Mouse Detail Modal -->
    <MouseDetailModal
      v-model="showMouseDetailModal"
      :mouse-code="selectedMouseCode"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { transferRequestsApi, miceApi, strainsApi, claimersApi, cagesApi, settingsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClaimerColors } from '@/composables/useClaimerColors'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import ExcelSortHeader from '@/components/ExcelSortHeader.vue'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const { getClaimerTagStyle, fetchClaimerColors } = useClaimerColors()

const loading = ref(false)
const requests = ref([])
const strainOptions = ref([])
const roomOptions = ref([])
const transferRoomOptions = ref(['东五', '东四'])
const claimerOptions = ref([])
const claimerOptionsLoading = ref(false)

// Excel-Style Table Sorting State
const sortConfig = reactive({
  prop: '',
  order: '' // 'asc' | 'desc' | ''
})

const columnMeta = {
  seq: { label: '序号', ascText: '从小到大', descText: '从大到小' },
  request_date: { label: '申请日期', ascText: '从早到晚', descText: '从晚到早' },
  demander: { label: '需求者', ascText: '姓名升序', descText: '姓名降序' },
  strain: { label: '小鼠品系', ascText: '品系升序', descText: '品系降序' },
  age_gender_req: { label: '要求年龄/性别', ascText: '周龄小到大', descText: '周龄大到小' },
  target_room: { label: '期望转入鼠房', ascText: '名称升序', descText: '名称降序' },
  cage_count: { label: '笼位', ascText: '从少到多', descText: '从多到少' },
  source_room: { label: '转出鼠房', ascText: '名称升序', descText: '名称降序' },
  status: { label: '状态', ascText: '流转阶段', descText: '逆流转阶段' }
}

function toggleSort(prop, order) {
  if (sortConfig.prop === prop && sortConfig.order === order) {
    clearSort()
  } else {
    sortConfig.prop = prop
    sortConfig.order = order
  }
}

function clearSort() {
  sortConfig.prop = ''
  sortConfig.order = ''
}

function getAgeReqSortKey(val) {
  if (!val || val === '/' || val === '-') return { rank: 999, text: '' }
  const s = String(val).trim()
  const monMatch = s.match(/(\d+(?:\.\d+)?)\s*(?:mon|月|months?)/i)
  if (monMatch) return { rank: Number(monMatch[1]) * 4.3, text: s }
  const weekMatch = s.match(/(\d+(?:\.\d+)?)\s*(?:周|w|weeks?)/i)
  if (weekMatch) return { rank: Number(weekMatch[1]), text: s }
  if (s.includes('幼') || s.includes('乳')) return { rank: 3, text: s }
  if (s.includes('成')) return { rank: 10, text: s }
  if (s.includes('老')) return { rank: 50, text: s }
  return { rank: 25, text: s }
}

const sortedRequests = computed(() => {
  if (!sortConfig.prop || !sortConfig.order) {
    return requests.value
  }
  const { prop, order } = sortConfig
  const list = requests.value
  if (!list.length) return []

  // Precompute comparable sort keys in a single pass O(N)
  const mapped = list.map(item => {
    let key
    if (prop === 'seq') {
      key = parseInt(item.seq, 10) || item.id || 0
    } else if (prop === 'request_date') {
      key = item.request_date || ''
    } else if (prop === 'age_gender_req') {
      key = getAgeReqSortKey(item.age_gender_req)
    } else if (prop === 'target_room') {
      key = item.target_room || ''
    } else if (prop === 'demander') {
      key = item.demander || ''
    } else if (prop === 'strain') {
      key = item.strain || ''
    } else if (prop === 'cage_count') {
      key = Number(item.cage_count) || 1
    } else if (prop === 'source_room') {
      key = item.source_room || ''
    } else if (prop === 'status') {
      const statusOrder = { '申请中': 1, '进行中': 2, '已转': 3, '取消': 4 }
      key = statusOrder[item.status] || 99
    } else {
      key = String(item[prop] || '')
    }
    return { item, key }
  })

  // Fast key comparisons
  mapped.sort((a, b) => {
    let cmp = 0
    if (prop === 'seq' || prop === 'cage_count' || prop === 'status') {
      cmp = a.key - b.key
    } else if (prop === 'request_date') {
      if (!a.key && !b.key) cmp = 0
      else if (!a.key) cmp = 1
      else if (!b.key) cmp = -1
      else cmp = a.key.localeCompare(b.key)
    } else if (prop === 'age_gender_req') {
      if (a.key.rank !== b.key.rank) {
        cmp = a.key.rank - b.key.rank
      } else {
        cmp = a.key.text.localeCompare(b.key.text, 'zh-CN')
      }
    } else {
      cmp = String(a.key).localeCompare(String(b.key), 'zh-CN')
    }
    return order === 'asc' ? cmp : -cmp
  })

  return mapped.map(entry => entry.item)
})

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
  demander: '',
  status: ''
})

// Submit Dialog
const showSubmitDialog = ref(false)
const submitFormRef = ref(null)
const submitting = ref(false)
const submitForm = reactive({
  demander: '',
  strain: '',
  age_gender_req: '成年/无要求',
  target_room: '东五',
  cage_count: 1,
  feedback: ''
})

const submitRules = {
  demander: [{ required: true, whitespace: true, message: '请选择或输入需求者姓名', trigger: 'change' }],
  strain: [{ required: true, message: '请输入小鼠品系', trigger: 'blur' }],
  target_room: [{ required: true, whitespace: true, message: '请选择或输入期望转入鼠房', trigger: 'change' }]
}

const showTransferRoomSettings = ref(false)
const newTransferRoomName = ref('')
const addingTransferRoom = ref(false)
const savingTransferRoom = ref('')
const deletingTransferRoom = ref('')
const transferRoomDrafts = reactive({})

// Process Dialog (Admin)
const showProcessDialog = ref(false)
const currentReq = ref(null)
const processing = ref(false)
const processForm = reactive({
  status: '已转',
  strain: '',
  source_room: '枫林',
  mouse_codes: '',
  mouse_gender: 'M',
  feedback: ''
})
const candidateTableRef = ref(null)
const candidateLoading = ref(false)
const candidateMiceRaw = ref([])
const selectedCandidateCodes = ref([])
const candidateFilters = reactive({
  gender: '',
  ageOperator: '>=',
  ageWeeks: '',
  keyword: ''
})
let syncingCandidateSelection = false

const candidateMice = computed(() => {
  const keyword = candidateFilters.keyword.trim().toLowerCase()
  const targetAgeWeeks = parseTargetAgeWeeks(candidateFilters.ageWeeks)
  const op = candidateFilters.ageOperator || '>='

  return candidateMiceRaw.value.filter((mouse) => {
    if (mouse.assigned_to_request) return true
    const mouseRoom = mouse.cage_room || mouse.source_room || ''
    if (processForm.source_room && mouseRoom !== processForm.source_room) return false
    if (candidateFilters.gender && normalizeGender(mouse.gender) !== candidateFilters.gender) return false
    if (targetAgeWeeks !== null) {
      const mouseAgeWeeks = Number(mouse.age_weeks)
      if (!Number.isFinite(mouseAgeWeeks)) return false

      if (op === '>') {
        if (!(mouseAgeWeeks > targetAgeWeeks + 0.05)) return false
      } else if (op === '>=') {
        if (!(mouseAgeWeeks >= targetAgeWeeks - 0.05)) return false
      } else if (op === '=') {
        if (Math.abs(mouseAgeWeeks - targetAgeWeeks) > 0.5) return false
      } else if (op === '<') {
        if (!(mouseAgeWeeks < targetAgeWeeks - 0.05)) return false
      } else if (op === '<=') {
        if (!(mouseAgeWeeks <= targetAgeWeeks + 0.05)) return false
      }
    }
    if (!keyword) return true
    return [mouse.mouse_code, mouse.strain, mouse.cage_code, mouse.cage_room, mouse.source_room]
      .some(value => String(value || '').toLowerCase().includes(keyword))
  })
})

const candidateFilterHint = computed(() => {
  const opLabelMap = {
    '>': '大于',
    '>=': '大于等于 (≥)',
    '=': '等于 (=，约±0.5周)',
    '<': '小于',
    '<=': '小于等于 (≤)'
  }
  const opText = opLabelMap[candidateFilters.ageOperator] || '大于等于'
  const ageText = candidateFilters.ageWeeks !== '' ? `、周龄 ${opText} ${candidateFilters.ageWeeks} 周` : ''
  const roomText = processForm.source_room ? `“${processForm.source_room}”鼠房内` : '所选鼠房内'
  if (isAnyStrainRequest(processForm.strain)) {
    return `${roomText}的“废鼠”按不限品系处理；可按性别${ageText}快速筛选`
  }
  return `展示${roomText}符合品系、性别${ageText}及未领取状态的候选小鼠`
})

function isAnyStrainRequest(strain) {
  return String(strain || '').trim() === '废鼠'
}

function normalizeGender(gender) {
  const value = String(gender || '').trim().toUpperCase()
  if (['M', 'MALE', '雄', '雄鼠', '公'].includes(value)) return 'M'
  if (['F', 'FEMALE', '雌', '雌鼠', '母'].includes(value)) return 'F'
  return value
}

function inferRequestedGender(requirement) {
  const value = String(requirement || '')
  if (/雄|公|\bM\b/i.test(value)) return 'M'
  if (/雌|母|\bF\b/i.test(value)) return 'F'
  return ''
}

function inferRequestedAgeOperator(requirement) {
  const value = String(requirement || '')
  if (/以上|大于|不小于|超|>=|≥/i.test(value)) return '>='
  if (/>/i.test(value)) return '>'
  if (/以下|小于|不大于|不足|<=|≤/i.test(value)) return '<='
  if (/</i.test(value)) return '<'
  if (/等于|=|恰好/i.test(value)) return '='
  return '>='
}

function inferRequestedAgeWeeks(requirement) {
  const value = String(requirement || '')
  const weekMatch = value.match(/(\d+(?:\.\d+)?)\s*(?:周|w|weeks?)/i)
  if (weekMatch) return weekMatch[1]
  const monMatch = value.match(/(\d+(?:\.\d+)?)\s*(?:mon|月|months?)/i)
  if (monMatch) return String(Math.round(Number(monMatch[1]) * 4.3))
  return ''
}

function parseTargetAgeWeeks(value) {
  if (value === '' || value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

function formatMouseAge(mouse) {
  if (mouse.age_weeks !== null && mouse.age_weeks !== undefined) return `${mouse.age_weeks} 周`
  return mouse.dob ? `生于 ${mouse.dob}` : '-'
}

function parseMouseCodes(value) {
  return [...new Set(String(value || '').split(/[,，、\s]+/).map(code => code.trim()).filter(Boolean))]
}

async function loadStrainOptions() {
  try {
    const strains = await strainsApi.listStrains()
    strainOptions.value = strains.map(item => item.name).filter(Boolean)
  } catch (e) {
    console.error(e)
  }
}

function applyTransferRoomOptions(rooms) {
  const normalized = [...new Set((Array.isArray(rooms) ? rooms : [])
    .map(room => String(room || '').trim())
    .filter(Boolean))]
  transferRoomOptions.value = normalized.length ? normalized : ['东五', '东四']
  for (const key of Object.keys(transferRoomDrafts)) delete transferRoomDrafts[key]
  for (const room of transferRoomOptions.value) transferRoomDrafts[room] = room
}

async function loadTransferRoomOptions() {
  try {
    const settings = await settingsApi.getPublic()
    applyTransferRoomOptions(settings.transfer_rooms)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载期望转入鼠房选项失败')
  }
}

async function openTransferRoomSettings() {
  await loadTransferRoomOptions()
  newTransferRoomName.value = ''
  showTransferRoomSettings.value = true
}

async function addTransferRoomOption() {
  const name = newTransferRoomName.value.trim()
  if (!name) return ElMessage.warning('请输入鼠房名称')
  addingTransferRoom.value = true
  try {
    const result = await settingsApi.addTransferRoom({ name })
    applyTransferRoomOptions(result.transfer_rooms)
    newTransferRoomName.value = ''
    ElMessage.success('鼠房选项已新增')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '新增鼠房选项失败')
  } finally {
    addingTransferRoom.value = false
  }
}

async function renameTransferRoomOption(oldName) {
  const name = String(transferRoomDrafts[oldName] || '').trim()
  if (!name || name === oldName) return
  savingTransferRoom.value = oldName
  try {
    const result = await settingsApi.renameTransferRoom(oldName, { name })
    applyTransferRoomOptions(result.transfer_rooms)
    if (submitForm.target_room === oldName) submitForm.target_room = name
    ElMessage.success('鼠房选项已重命名')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重命名失败')
  } finally {
    savingTransferRoom.value = ''
  }
}

async function deleteTransferRoomOption(name) {
  deletingTransferRoom.value = name
  try {
    const result = await settingsApi.deleteTransferRoom(name)
    applyTransferRoomOptions(result.transfer_rooms)
    if (submitForm.target_room === name) submitForm.target_room = transferRoomOptions.value[0] || ''
    ElMessage.success('鼠房选项已删除')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    deletingTransferRoom.value = ''
  }
}

async function loadRoomOptions() {
  try {
    const rooms = await cagesApi.listRooms({ include_categories: true })
    const categoryOrder = { '繁育鼠房': 0, '临时鼠房': 1, '实验鼠房': 2, '使用鼠房': 2 }
    const breedingRoomRank = (name) => {
      if (name.includes('实验动物楼')) return 0
      if (name.includes('江湾发育所')) return 1
      return 99
    }
    roomOptions.value = [...rooms]
      .sort((a, b) => {
        const categoryDiff = (categoryOrder[a.category] ?? 99) - (categoryOrder[b.category] ?? 99)
        if (categoryDiff) return categoryDiff
        if (a.category === '繁育鼠房') {
          const roomDiff = breedingRoomRank(a.name) - breedingRoomRank(b.name)
          if (roomDiff) return roomDiff
        }
        return a.name.localeCompare(b.name, 'zh-CN')
      })
      .map(room => room.name)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载鼠房列表失败')
  }
}

async function loadCandidateMice() {
  syncingCandidateSelection = true
  candidateMiceRaw.value = []
  if (!processForm.strain || !processForm.source_room) {
    await nextTick()
    syncingCandidateSelection = false
    return
  }

  candidateLoading.value = true
  try {
    const params = {
      page: 1,
      page_size: 500,
      in_cage: true,
      room: processForm.source_room
    }
    if (!isAnyStrainRequest(processForm.strain)) params.strain = processForm.strain
    const [res, assigned] = await Promise.all([
      miceApi.listMice(params),
      transferRequestsApi.getAssignedMice(currentReq.value.id)
    ])
    const currentCodes = new Set(parseMouseCodes(processForm.mouse_codes))
    const available = res.items.filter(mouse => {
      if (!mouse.cage_id || mouse.status === '出笼') return false
      const unavailable = ['已领用', '死亡'].includes(mouse.status)
      return (!mouse.owner_id && !mouse.owner_name && !unavailable) || currentCodes.has(mouse.mouse_code)
    })
    candidateMiceRaw.value = [...new Map([...available, ...assigned].map(mouse => [mouse.id, mouse])).values()]
    await syncCandidateSelectionFromCodes()
  } catch (e) {
    ElMessage.error('加载候选小鼠失败')
  } finally {
    candidateLoading.value = false
    syncingCandidateSelection = false
  }
}

function handleCandidateSelection(rows) {
  if (syncingCandidateSelection) return
  const previousSelected = new Set(selectedCandidateCodes.value)
  const manualCodes = parseMouseCodes(processForm.mouse_codes).filter(code => !previousSelected.has(code))
  selectedCandidateCodes.value = rows.map(row => row.mouse_code)
  processForm.mouse_codes = [...new Set([...manualCodes, ...selectedCandidateCodes.value])].join(', ')

  const genders = [...new Set(rows.map(row => normalizeGender(row.gender)).filter(value => ['M', 'F'].includes(value)))]
  if (genders.length === 1) processForm.mouse_gender = genders[0]
  if (genders.length > 1) processForm.mouse_gender = 'M/F'
}

async function syncCandidateSelectionFromCodes() {
  await nextTick()
  if (!candidateTableRef.value) return
  const codes = new Set(parseMouseCodes(processForm.mouse_codes))
  syncingCandidateSelection = true
  candidateTableRef.value.clearSelection()
  candidateMice.value.forEach(row => {
    if (codes.has(row.mouse_code)) candidateTableRef.value.toggleRowSelection(row, true)
  })
  selectedCandidateCodes.value = candidateMice.value
    .filter(row => codes.has(row.mouse_code))
    .map(row => row.mouse_code)
  syncingCandidateSelection = false
}

async function loadRequests() {
  loading.value = true
  try {
    const params = {
      demander: filters.demander || undefined,
      status: filters.status || undefined
    }
    requests.value = await transferRequestsApi.listRequests(params)
  } catch (e) {
    ElMessage.error('加载转鼠需求表失败')
  } finally {
    loading.value = false
  }
}

async function loadClaimerOptions() {
  claimerOptionsLoading.value = true
  try {
    claimerOptions.value = await claimersApi.listClaimers()
  } catch (e) {
    ElMessage.error('加载课题组成员失败，仍可手动输入姓名')
  } finally {
    claimerOptionsLoading.value = false
  }
}

function openSubmitDialog() {
  Object.assign(submitForm, {
    demander: '', // 默认姓名为空，由需求者自己填写
    strain: '',
    age_gender_req: '成年/无要求',
    target_room: transferRoomOptions.value[0] || '',
    cage_count: 1,
    feedback: ''
  })
  if (submitFormRef.value) {
    submitFormRef.value.clearValidate()
  }
  showSubmitDialog.value = true
  loadClaimerOptions()
}

async function handleSubmitRequest() {
  if (!submitFormRef.value) return
  await submitFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const roomResult = await settingsApi.addTransferRoom({ name: submitForm.target_room.trim() })
      applyTransferRoomOptions(roomResult.transfer_rooms)
      await transferRequestsApi.createRequest(submitForm)
      ElMessage.success('转鼠需求已成功提交，请等待管理员处理！')
      showSubmitDialog.value = false
      loadRequests()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '提交失败')
    } finally {
      submitting.value = false
    }
  })
}

async function openProcessDialog(row) {
  if (roomOptions.value.length === 0) await loadRoomOptions()
  currentReq.value = row
  const savedSourceRoom = String(row.source_room || '').trim()
  Object.assign(processForm, {
    status: row.status === '申请中' ? '已转' : row.status,
    strain: row.strain || '',
    source_room: roomOptions.value.includes(savedSourceRoom) ? savedSourceRoom : (roomOptions.value[0] || ''),
    mouse_codes: row.mouse_codes || '',
    mouse_gender: row.mouse_gender || 'M',
    feedback: row.feedback || ''
  })
  candidateFilters.gender = inferRequestedGender(row.age_gender_req)
  candidateFilters.ageOperator = inferRequestedAgeOperator(row.age_gender_req)
  candidateFilters.ageWeeks = inferRequestedAgeWeeks(row.age_gender_req)
  candidateFilters.keyword = ''
  selectedCandidateCodes.value = []
  showProcessDialog.value = true
  await loadCandidateMice()
}

async function submitProcess() {
  if (!processForm.strain.trim()) {
    ElMessage.warning('请选择或输入小鼠品系')
    return
  }
  if (processForm.status === '已转' && parseMouseCodes(processForm.mouse_codes).length === 0 && currentReq.value.status !== '已转') {
    ElMessage.warning('请勾选候选小鼠或直接输入小鼠编号')
    return
  }
  processing.value = true
  try {
    await transferRequestsApi.processRequest(currentReq.value.id, processForm)
    ElMessage.success('转鼠需求已成功审批处理！')
    showProcessDialog.value = false
    loadRequests()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '处理失败')
  } finally {
    processing.value = false
  }
}

async function handleDelete(id) {
  try {
    await transferRequestsApi.deleteRequest(id)
    ElMessage.success('删除成功')
    loadRequests()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  fetchClaimerColors()
  await Promise.all([
    loadStrainOptions(),
    loadRoomOptions(),
    loadTransferRoomOptions(),
    loadRequests()
  ])

  const approvalId = Number(route.query.approve)
  if (authStore.isAdmin && Number.isInteger(approvalId) && approvalId > 0) {
    const request = requests.value.find(item => item.id === approvalId)
    if (request && ['申请中', '进行中'].includes(request.status)) {
      await openProcessDialog(request)
    } else {
      ElMessage.warning('该转鼠需求已处理或不存在')
    }

    const query = { ...route.query }
    delete query.approve
    router.replace({ query })
  }
})
</script>

<style scoped>
:deep(.el-form-item__label) {
  white-space: nowrap !important;
  font-weight: 500;
}

.transfer-room-field,
.transfer-room-add-row,
.transfer-room-setting-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.transfer-room-add-row {
  margin-bottom: 8px;
}

.transfer-room-setting-row {
  padding: 8px 0;
  border-top: 1px solid #ebeef5;
}

.transfer-room-setting-row .el-input {
  flex: 1;
}

.candidate-panel {
  margin: 0 0 18px 125px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #f8fbff;
}

.candidate-gender {
  font-size: 18px;
  font-weight: 700;
}

.candidate-gender-male {
  color: #3b82f6;
}

.candidate-gender-female {
  color: #ec4899;
}

.candidate-toolbar {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.candidate-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.candidate-filters > * {
  flex-shrink: 0;
}

@media (max-width: 760px) {
  .candidate-panel {
    margin-left: 0;
  }

  .candidate-toolbar {
    flex-direction: column;
  }
}
</style>
