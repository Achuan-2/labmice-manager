<template>
  <div class="cages-page">
    <!-- Header Controls -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <span class="text-sm font-semibold text-gray-600">鼠房分类</span>
        <el-radio-group v-model="activeCategory" @change="changeCategory">
          <el-radio-button value="">全部分类</el-radio-button>
          <el-radio-button v-for="category in roomCategories" :key="category" :value="category">{{ category }}</el-radio-button>
        </el-radio-group>
        <el-button v-if="authStore.isAdmin" class="room-settings-button" plain @click="openManageRooms">
          <el-icon class="mr-1"><Setting /></el-icon> 管理鼠房
        </el-button>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <!-- Room Tabs -->
        <el-radio-group v-model="activeRoom" @change="changeRoom">
          <el-radio-button value="">{{ activeCategory ? '本类全部鼠房' : '全部鼠房' }}</el-radio-button>
          <el-radio-button v-for="r in categoryRooms" :key="r" :value="r">{{ r }}</el-radio-button>
        </el-radio-group>

        <div class="flex flex-wrap items-center gap-3">
          <el-select v-model="cageGenderFilter" clearable placeholder="全部鼠笼性别" style="width: 140px">
            <el-option label="♂ 雄笼" value="M" />
            <el-option label="♀ 雌笼" value="F" />
            <el-option label="♂♀ 混笼" value="M/F" />
          </el-select>
          <el-select v-model="cageCodeFilter" clearable filterable placeholder="全部笼位" style="width: 140px">
            <el-option v-for="code in cageCodeOptions" :key="code" :label="code" :value="code" />
          </el-select>
          <el-input
            v-model="searchCode"
            placeholder="搜索笼号或品系"
            clearable
            prefix-icon="Search"
            style="width: 200px"
          />
          <el-checkbox v-model="onlyWithMice">仅显示有鼠笼位</el-checkbox>
          <el-button v-if="authStore.isAdmin" type="primary" plain @click="openAddCageDialog">
            <el-icon class="mr-1"><Plus /></el-icon> 新建笼位
          </el-button>
          <el-button :loading="exporting" @click="handleExport">
            <el-icon class="mr-1"><Download /></el-icon> 导出笼位
          </el-button>
        </div>
      </div>
    </div>

    <!-- Cages Grid -->
    <div v-loading="loading">
      <div v-if="filteredCages.length === 0" class="bg-white p-12 text-center rounded-xl border border-gray-200 text-gray-400">
        没有找到符合条件的笼位
      </div>

      <div v-else class="cage-grid grid grid-cols-4 gap-4">
        <div
          v-for="cage in pagedCages"
          :key="cage.id"
          class="cage-card bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md transition flex flex-col justify-between"
          :class="{ 'border-blue-300': cage.mouse_count > 0, 'border-gray-200': cage.mouse_count === 0 }"
        >
          <!-- Cage Header -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="text-xl font-bold font-mono text-gray-800">{{ cage.cage_code }}</span>
                <el-tag size="small" effect="plain" type="info">{{ cage.room }}</el-tag>
              </div>

              <!-- Occupancy Indicator -->
              <el-tag
                size="small"
                :type="cage.mouse_count === 0 ? 'info' : (cage.mouse_count > cage.capacity ? 'danger' : 'success')"
                effect="dark"
              >
                {{ cage.mouse_count }} / {{ cage.capacity }} 只
              </el-tag>
            </div>

            <!-- Strain & Gender -->
            <div class="flex items-center gap-2 text-xs mb-3">
              <span class="font-semibold text-blue-700 truncate max-w-[140px]" :title="cage.strain">
                {{ cage.strain || '未指定品系' }}
              </span>
              <el-tag size="small" :type="genderTagType(cage.gender)" effect="light">
                <template v-if="cage.gender === 'M'"><span class="male-symbol">♂</span> 雄</template>
                <template v-else-if="cage.gender === 'F'"><span class="female-symbol">♀</span> 雌</template>
                <template v-else-if="cage.gender === 'M/F' || cage.gender === '混合'"><span class="male-symbol">♂</span><span class="female-symbol">♀</span> 混合</template>
                <template v-else>未知</template>
              </el-tag>
            </div>

            <div v-if="cageMatingDate(cage)" class="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded mb-2">
              💑 合笼日期: {{ cageMatingDate(cage) }}
            </div>
            <div v-if="cageLitterDates(cage).length" class="text-xs text-purple-700 bg-purple-50 px-2 py-1 rounded mb-2">
              <div class="font-semibold mb-1">🐣 生鼠批次</div>
              <div v-for="date in cageLitterDates(cage)" :key="date" class="flex justify-between gap-2">
                <span>{{ date }} · {{ litterMouseCount(cage, date) }}只</span><span class="text-purple-500">{{ weaningDate(date) }} 满21天</span>
              </div>
            </div>

            <!-- Mice inside this cage (Chips) -->
            <div class="text-xs text-gray-500 font-medium mb-1.5 flex justify-between items-center">
              <span>在笼小鼠:</span>
              <span v-if="cage.mouse_count > 0" class="text-gray-400">
                (已领用: {{ cage.mice.filter(m => m.owner_name).length }})
              </span>
            </div>

            <div class="mice-chips flex flex-col gap-1.5 mb-3 min-h-[60px] max-h-[140px] overflow-y-auto bg-gray-50 p-2 rounded">
              <div v-if="cage.mouse_count === 0" class="text-xs text-gray-400 text-center py-3">
                空笼位
              </div>
              <div
                v-for="m in cage.mice"
                :key="m.id"
                class="mouse-item flex items-center justify-between text-xs bg-white p-1.5 rounded border border-gray-200"
                :class="mouseGenderItemClass(m.gender)"
              >
                <div
                  class="mouse-summary flex items-center gap-1.5 cursor-pointer text-blue-700 hover:text-blue-900 group"
                  title="点击查看该小鼠详细档案、父母系谱及流转记录"
                  @click.stop="openMouseDetail(m)"
                >
                  <span class="font-mono font-bold group-hover:underline">{{ m.mouse_code }}</span>
                  <span v-if="m.gender === 'M'" class="male-symbol">♂</span>
                  <span v-else-if="m.gender === 'F'" class="female-symbol">♀</span>
                  <span v-if="m.age_weeks !== null" class="mouse-age text-gray-400">({{ m.age_weeks }}周)</span>
                </div>

                <!-- Owner Badge -->
                <div class="mouse-owner">
                  <el-tag
                    v-if="m.owner_name"
                    size="small"
                    :style="getClaimerTagStyle(m.owner_name)"
                    class="text-xs font-medium border"
                  >
                    👤 {{ m.owner_name }}
                  </el-tag>
                  <el-tag v-else size="small" type="info" effect="plain" class="text-xs text-gray-400">
                    未分配
                  </el-tag>
                </div>
              </div>
            </div>

            <div v-if="cage.observation || cage.notes" class="text-xs text-gray-500 bg-gray-50 p-1.5 rounded mb-2 truncate" :title="cage.observation || cage.notes">
              📝 {{ cage.observation || cage.notes }}
            </div>
          </div>

          <!-- Cage Actions -->
          <div class="pt-2 border-t border-gray-100 flex items-center justify-between">
            <!-- Fast Set Owner for this cage -->
            <el-button
              type="primary"
              size="small"
              link
              :disabled="cage.mouse_count === 0 || !authStore.isAdmin"
              @click="openSetOwnerForCage(cage)"
            >
              <el-icon class="mr-0.5"><User /></el-icon> 设置领取人
            </el-button>

            <div class="flex items-center gap-1">
              <el-button
                size="small"
                type="info"
                link
                :disabled="!authStore.isAdmin"
                @click="openEditCageDialog(cage)"
              >
                编辑
              </el-button>
              <el-popconfirm
                title="确定删除此笼位吗？在笼小鼠将被移出"
                @confirm="handleDeleteCage(cage.id)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    type="danger"
                    link
                    :disabled="!authStore.isAdmin"
                  >
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-pagination
      v-if="filteredCages.length > 0"
      v-model:current-page="currentPage"
      :page-size="pageSize"
      :total="filteredCages.length"
      layout="total, prev, pager, next"
      class="mt-4 flex justify-center"
    />

    <!-- Set Owner Dialog for Cage Mice -->
    <SetOwnerDialog
      v-model="showSetOwnerDialog"
      :mice="currentCageMice"
      @success="onSetOwnerSuccess"
    />

    <!-- Add/Edit Cage Dialog -->
    <el-dialog v-model="showCageDialog" :title="isEdit ? '编辑笼位' : '新建笼位'" width="min(720px, 94vw)" :close-on-click-modal="!cageMouseBusy" :close-on-press-escape="!cageMouseBusy" :show-close="!cageMouseBusy">
      <el-form :model="cageForm" label-width="80px">
        <el-form-item label="鼠房" required>
          <el-select v-model="cageForm.room" filterable allow-create placeholder="选择或输入鼠房" style="width: 100%">
            <el-option v-for="r in roomOptions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item :label="isEdit ? '笼位号' : '笼位编号'" required>
          <el-input
            v-model="cageForm.cage_code"
            :type="isEdit ? 'text' : 'textarea'"
            :rows="isEdit ? undefined : 3"
            :placeholder="isEdit ? '如 7A' : '可输入多个编号，如：8A，10A，20A'"
          />
          <div v-if="!isEdit" class="text-xs text-gray-500 mt-1">
            支持中文/英文逗号、顿号、空格或换行分隔；当前识别 {{ parsedNewCageCodes.length }} 个笼位。
          </div>
        </el-form-item>
        <el-form-item label="品系">
          <StrainSelect v-model="cageForm.strain" />
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="cageForm.gender">
            <el-radio value="M">雄</el-radio>
            <el-radio value="F">雌</el-radio>
            <el-radio value="M/F">混合/合笼</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="合笼日期">
          <el-date-picker v-model="cageForm.mating_date" type="date" value-format="YYYY-MM-DD" placeholder="选择合笼日期" />
        </el-form-item>
        <el-form-item label="观察记录">
          <el-input v-model="cageForm.observation" type="textarea" :rows="2" placeholder="观察记录" />
        </el-form-item>
        <el-form-item v-if="cageForm.gender === 'M/F' || cageForm.gender === '混合'" label="生鼠批次">
          <div class="litter-batches">
            <div class="litter-add-row">
              <el-date-picker v-model="newLitterBirthDate" type="date" value-format="YYYY-MM-DD" placeholder="选择本批出生日期" style="flex: 1" />
              <el-button type="primary" plain :disabled="!newLitterBirthDate || cageMouseBusy" @click="addLitterBatch">新增批次</el-button>
            </div>
            <div v-if="cageForm.litter_birth_dates.length" class="litter-batch-list">
              <div v-for="date in cageForm.litter_birth_dates" :key="date" class="litter-batch-item">
                <div>
                  <div class="font-medium text-purple-800">{{ date }}</div>
                  <div class="text-xs text-gray-500">本笼已绑定 {{ litterMouseCount({ mice: editingCageMice }, date) }} 只 · {{ weaningDate(date) }} 满 21 天</div>
                  <el-tag v-if="isLitterDue(date)" size="small" type="warning" class="mt-1">已满21天，可批量换笼</el-tag>
                </div>
                <div class="flex items-center gap-1">
                  <el-button v-if="isEdit" type="primary" size="small" :disabled="cageMouseBusy" @click="openAddCageMouse(date)">新增鼠</el-button>
                  <el-button v-if="isEdit" type="info" size="small" :disabled="!litterMouseCount({ mice: editingCageMice }, date)" @click="openLitterMice(date)">查看鼠（{{ litterMouseCount({ mice: editingCageMice }, date) }}只）</el-button>
                  <el-button v-if="isEdit" type="success" size="small" :disabled="cageMouseBusy || !isLitterDue(date) || !litterMouseCount({ mice: editingCageMice }, date)" :title="splitLitterButtonTitle(date)" @click="openSplitLitterBatch(date)">批量换笼（{{ litterMouseCount({ mice: editingCageMice }, date) }}只）</el-button>
                  <el-button type="danger" size="small" link :disabled="cageMouseBusy" @click="removeLitterBatch(date)">删除</el-button>
                </div>
              </div>
            </div>
            <div v-else class="text-xs text-gray-500">可记录多批生鼠日期；保存笼位后，可从每个批次直接新增本批小鼠。</div>
          </div>
        </el-form-item>
      </el-form>
      <section v-if="isEdit" class="mt-4 border-t border-gray-200 pt-4">
        <div class="flex items-center justify-between mb-2">
          <span class="font-semibold">在笼小鼠（{{ editingCageMice.length }} 只）</span>
          <div class="flex items-center gap-2">
            <el-button
              type="warning"
              plain
              size="small"
              :disabled="cageMouseBusy || selectedEditingCageMice.length === 0"
              @click="openBatchEditMice"
            >
              批量编辑{{ selectedEditingCageMice.length ? `（${selectedEditingCageMice.length}）` : '' }}
            </el-button>
            <el-button
              type="primary"
              plain
              size="small"
              :disabled="cageMouseBusy || selectedEditingCageMice.length === 0"
              @click="openBatchMoveMice"
            >
              批量换笼{{ selectedEditingCageMice.length ? `（${selectedEditingCageMice.length}）` : '' }}
            </el-button>
            <el-button type="primary" size="small" :disabled="cageMouseBusy" @click="openAddCageMouse()">新增鼠</el-button>
          </div>
        </div>
        <div class="text-xs text-gray-500 mb-2">点击小鼠编号可查看和编辑档案；勾选小鼠可批量修改品系、出生日期、性别或批量换笼。新增、编辑、换笼和移除立即生效。移除只清除当前笼位，小鼠档案、基因鉴定、领取人与历史记录均保留。</div>
        <el-table :data="editingCageMice" max-height="240" empty-text="当前笼位暂无小鼠" @selection-change="handleEditingCageSelection">
          <el-table-column type="selection" width="44" />
          <el-table-column prop="mouse_code" label="小鼠编号" min-width="100">
            <template #default="{ row }">
              <el-button type="primary" link class="font-mono font-bold" title="查看和编辑小鼠档案" @click.stop="openMouseDetail(row)">
                {{ row.mouse_code }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="strain" label="品系" min-width="100" />
          <el-table-column prop="gender" label="性别" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="genderTagType(row.gender)" effect="light">{{ genderLabel(row.gender) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="age_weeks" label="年龄" width="85">
            <template #default="{ row }">{{ row.age_weeks == null ? '-' : `${row.age_weeks}周` }}</template>
          </el-table-column>
          <el-table-column prop="owner_name" label="领取人" min-width="85" />
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button type="primary" link :disabled="cageMouseBusy" @click="openMoveMouse(row)">换笼</el-button>
              <el-popconfirm :title="`将 ${row.mouse_code} 移出本笼？只清除笼位，小鼠档案将完整保留。`" @confirm="removeCageMouse(row)">
                <template #reference>
                  <el-button type="warning" link :disabled="cageMouseBusy">移除鼠</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="showAddCageMouse" :title="cageMouseForm.dob ? `新增鼠 · ${cageMouseForm.dob} 出生批次` : '新增鼠'" width="min(520px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!cageMouseBusy" :show-close="!cageMouseBusy">
          <div class="text-sm text-gray-500 mb-4">添加到：{{ editingCageRoom }} · {{ editingCageCode }}</div>
        <el-form :model="cageMouseForm" label-width="90px" :disabled="cageMouseBusy">
          <el-form-item label="新增数量" required>
            <el-input-number v-model="cageMouseForm.add_count" :min="1" :max="100" @change="updateCageMouseCodes" />
          </el-form-item>
          <el-form-item label="起始编号" required>
            <el-input v-model="cageMouseForm.start_code" placeholder="如 Z100" @input="updateCageMouseCodes" />
            <div class="text-xs text-gray-500">起始编号包含在本批内；输入 Z100、新增 5 只，将生成 Z100 至 Z104。</div>
          </el-form-item>
          <el-form-item label="编号列表" required>
            <el-input v-model="cageMouseForm.mouse_code" type="textarea" :rows="2" placeholder="自动生成后仍可手动调整，多个编号用逗号分隔" />
            <div class="text-xs text-gray-500">以下信息应用于全部新增小鼠，已存在的编号会跳过。</div>
          </el-form-item>
          <el-form-item label="品系"><StrainSelect v-model="cageMouseForm.strain" /></el-form-item>
          <el-form-item label="性别">
            <el-select v-model="cageMouseForm.gender" style="width: 100%">
              <el-option label="雄 (M)" value="M" /><el-option label="雌 (F)" value="F" /><el-option label="未知" value="未知" />
            </el-select>
          </el-form-item>
          <el-form-item label="出生日期"><el-date-picker v-model="cageMouseForm.dob" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="父母系谱">
            <el-input v-model="cageMouseForm.parents" placeholder="根据本笼混笼亲本自动生成，也可手动修改" />
            <div class="text-xs text-gray-500">从本笼雄鼠、雌鼠自动识别；已登记出生批次中的幼鼠不会作为亲本。</div>
          </el-form-item>
          <el-form-item label="备注"><el-input v-model="cageMouseForm.notes" type="textarea" :rows="2" /></el-form-item>
        </el-form>
          <template #footer>
            <el-button :disabled="cageMouseBusy" @click="showAddCageMouse = false">取消</el-button>
            <el-button type="primary" :loading="cageMouseBusy" @click="addCageMouse">确认新增到本笼</el-button>
          </template>
        </el-dialog>
      </section>
      <template #footer>
        <el-button :disabled="cageMouseBusy" @click="showCageDialog = false">{{ isEdit ? '关闭' : '取消' }}</el-button>
        <el-button type="primary" :loading="cageSaving" :disabled="cageMouseBusy" @click="submitCageForm">{{ isEdit ? '保存笼位信息' : '新增笼位' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showLitterMiceDialog"
      :title="`${viewingLitterDate} 出生批次 · 小鼠列表（${viewingLitterMice.length}只）`"
      width="min(720px, 94vw)"
      append-to-body
    >
      <el-table :data="viewingLitterMice" max-height="420" empty-text="该批次暂无在笼小鼠">
        <el-table-column prop="mouse_code" label="小鼠编号" min-width="115">
          <template #default="{ row }">
            <el-button type="primary" link class="font-mono font-bold" @click="openMouseDetail(row)">{{ row.mouse_code }}</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="strain" label="品系" min-width="130" />
        <el-table-column prop="gender" label="性别" width="80">
          <template #default="{ row }"><el-tag size="small" :type="genderTagType(row.gender)">{{ genderLabel(row.gender) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="age_weeks" label="周龄" width="80">
          <template #default="{ row }">{{ row.age_weeks == null ? '-' : `${row.age_weeks}周` }}</template>
        </el-table-column>
        <el-table-column prop="owner_name" label="领取人" min-width="100">
          <template #default="{ row }">{{ row.owner_name || '未分配' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }"><el-button type="primary" link @click="openMouseDetail(row)">查看档案</el-button></template>
        </el-table-column>
      </el-table>
      <template #footer><el-button @click="showLitterMiceDialog = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog
      v-model="showBatchEditMiceDialog"
      :title="`批量编辑小鼠（${batchEditingMice.length}只）`"
      width="min(520px, 94vw)"
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="!batchEditBusy"
      :show-close="!batchEditBusy"
    >
      <div class="text-sm text-gray-500 mb-4 break-all">已选择：{{ batchEditingMice.map(mouse => mouse.mouse_code).join('、') }}</div>
      <el-form class="batch-edit-form" label-width="140px" :disabled="batchEditBusy">
        <el-form-item>
          <template #label><el-checkbox v-model="batchEditForm.updateStrain">修改品系</el-checkbox></template>
          <StrainSelect
            v-model="batchEditForm.strain"
            placeholder="请选择或输入品系；清空可移除品系"
            :disabled="!batchEditForm.updateStrain"
          />
        </el-form-item>
        <el-form-item>
          <template #label><el-checkbox v-model="batchEditForm.updateDob">修改出生日期</el-checkbox></template>
          <el-date-picker
            v-model="batchEditForm.dob"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期；清空可移除日期"
            :disabled="!batchEditForm.updateDob"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item>
          <template #label><el-checkbox v-model="batchEditForm.updateGender">修改性别</el-checkbox></template>
          <el-select v-model="batchEditForm.gender" placeholder="请选择性别" :disabled="!batchEditForm.updateGender" style="width: 100%">
            <el-option label="雄 (M)" value="M" />
            <el-option label="雌 (F)" value="F" />
            <el-option label="未知" value="未知" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="text-xs text-gray-500">勾选要修改的字段；未勾选的字段会保持原值。</div>
      <template #footer>
        <el-button :disabled="batchEditBusy" @click="showBatchEditMiceDialog = false">取消</el-button>
        <el-button type="primary" :loading="batchEditBusy" @click="submitBatchEditMice">确认修改</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showMoveMouseDialog"
      :title="movingMice.length > 1 ? `批量换笼（${movingMice.length} 只）` : `小鼠换笼${movingMice[0] ? ` - ${movingMice[0].mouse_code}` : ''}`"
      width="460px"
      append-to-body
      :close-on-click-modal="!movingMouseBusy"
    >
      <el-form :model="moveMouseForm" label-width="90px">
        <el-form-item label="当前笼位">
          <span class="font-mono text-gray-600">{{ editingCageRoom }} · {{ editingCageCode }}</span>
        </el-form-item>
        <el-form-item label="已选小鼠">
          <div class="flex flex-wrap gap-1">
            <el-tag v-for="mouse in movingMice" :key="mouse.id" size="small" effect="plain">{{ mouse.mouse_code }}</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="目标鼠房" required>
          <el-select
            v-model="moveMouseForm.target_room"
            filterable
            placeholder="选择目标鼠房"
            style="width: 100%"
            @change="handleMoveRoomChange"
          >
            <el-option v-for="room in roomOptions" :key="room" :label="room" :value="room" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标笼位" required>
          <el-select
            v-model="moveMouseForm.target_cage_code"
            filterable
            allow-create
            default-first-option
            placeholder="选择已有笼位或输入新笼号"
            style="width: 100%"
          >
            <el-option
              v-for="target in targetCageOptions"
              :key="target.id"
              :label="`${target.cage_code}（${target.mouse_count || 0} 只）`"
              :value="target.cage_code"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="text-xs text-gray-500">换笼完成后会自动写入“领用与流转日志”。</div>
      <template #footer>
        <el-button :disabled="movingMouseBusy" @click="showMoveMouseDialog = false">取消</el-button>
        <el-button type="primary" :loading="movingMouseBusy" @click="submitMoveMouse">确认换笼{{ movingMice.length > 1 ? `（${movingMice.length} 只）` : '' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showSplitLitterDialog"
      :title="`${splitLitterDate} 出生批次 · 批量换笼`"
      width="min(900px, 96vw)"
      append-to-body
      :close-on-click-modal="!splitLitterBusy"
      :show-close="!splitLitterBusy"
    >
      <div class="split-bulk-bar">
        <span class="text-sm font-semibold">批量指定目标</span>
        <el-select v-model="splitBulkTarget.room" filterable placeholder="目标鼠房" style="width: 170px" @change="splitBulkTarget.cage_code = ''">
          <el-option v-for="room in roomOptions" :key="room" :label="room" :value="room" />
        </el-select>
        <el-select v-model="splitBulkTarget.cage_code" filterable allow-create default-first-option placeholder="目标笼位，可输入新笼号" style="width: 210px">
          <el-option v-for="cage in splitCageOptions(splitBulkTarget.room)" :key="cage.id" :label="`${cage.cage_code}（${cage.mouse_count || 0}只）`" :value="cage.cage_code" />
        </el-select>
        <el-button type="primary" plain :disabled="!splitSelectedRows.length || !splitBulkTarget.room || !splitBulkTarget.cage_code" @click="applySplitTarget">应用到选中小鼠（{{ splitSelectedRows.length }}）</el-button>
      </div>
      <div class="text-xs text-gray-500 mb-3">先勾选一部分小鼠并指定 X 笼，再勾选其余小鼠指定 Y 笼。也可以逐只修改目标。</div>
      <el-table ref="splitTableRef" :data="splitLitterRows" max-height="420" @selection-change="handleSplitSelection">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="mouse_code" label="小鼠编号" min-width="115" />
        <el-table-column prop="gender" label="性别" width="75" />
        <el-table-column label="目标鼠房" min-width="170">
          <template #default="{ row }">
            <el-select v-model="row.target_room" filterable placeholder="选择鼠房" style="width: 100%" @change="row.target_cage_code = ''">
              <el-option v-for="room in roomOptions" :key="room" :label="room" :value="room" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="目标笼位" min-width="210">
          <template #default="{ row }">
            <el-select v-model="row.target_cage_code" filterable allow-create default-first-option placeholder="选择或输入新笼号" style="width: 100%">
              <el-option v-for="cage in splitCageOptions(row.target_room)" :key="cage.id" :label="`${cage.cage_code}（${cage.mouse_count || 0}只）`" :value="cage.cage_code" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button :disabled="splitLitterBusy" @click="showSplitLitterDialog = false">取消</el-button>
        <el-button type="success" :loading="splitLitterBusy" @click="submitSplitLitterBatch">确认批量换笼</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showManageRooms" title="管理鼠房" width="min(720px, 94vw)">
      <div class="flex justify-end mb-3">
        <el-button type="success" :disabled="!!deletingRoom || !!reassigningRoom" @click="openAddRoomDialog">
          <el-icon class="mr-1"><Plus /></el-icon> 新增鼠房
        </el-button>
      </div>
      <div class="text-sm text-gray-500 mb-3">拖动鼠房到目标分类名称上，可调整鼠房分类。有小鼠的鼠房需先转移全部小鼠，才能删除。</div>
      <el-table v-loading="managingRoomsLoading" :data="managedRoomTree" row-key="treeKey" default-expand-all :tree-props="{ children: 'children' }" max-height="420" empty-text="暂无鼠房">
        <el-table-column prop="name" label="鼠房分类 / 鼠房" min-width="220">
          <template #default="{ row }">
            <div
              v-if="row.isCategory"
              class="room-category-drop-target"
              :class="{ 'is-drag-over': draggedRoom && dragTargetCategory === row.name }"
              @dragenter.prevent="handleRoomDragOver(row.name)"
              @dragover.prevent="handleRoomDragOver(row.name, $event)"
              @drop.prevent.stop="dropRoomIntoCategory(row.name)"
            >
              <span class="font-semibold">{{ row.name }}</span>
              <span class="room-category-count text-xs text-gray-400">{{ row.children.length }} 个鼠房</span>
              <span v-if="draggedRoom" class="room-drop-hint text-xs">放到此分类</span>
            </div>
            <div
              v-else
              class="managed-room-drag-item"
              :class="{ 'is-dragging': draggedRoom?.name === row.name }"
              :draggable="!reassigningRoom"
              @dragstart="startRoomDrag(row, $event)"
              @dragend="finishRoomDrag"
            >
              <span class="room-drag-handle" title="拖动调整分类">⋮⋮</span>
              <span>{{ row.name }}</span>
              <span v-if="reassigningRoom === row.name" class="text-xs text-gray-400">保存中…</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="cage_count" label="笼位数" width="80" />
        <el-table-column prop="mouse_count" label="小鼠数" width="80" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button v-if="!row.isCategory && row.mouse_count > 0" type="danger" link :disabled="!!deletingRoom || !!reassigningRoom" @click="ElMessage.warning(`该鼠房还有 ${row.mouse_count} 只小鼠，请先将全部小鼠转移后再删除`)">删除</el-button>
            <el-popconfirm v-else-if="!row.isCategory" :title="`确定删除鼠房 ${row.name} 及其 ${row.cage_count} 个空笼位吗？`" @confirm="deleteManagedRoom(row)">
              <template #reference><el-button type="danger" link :loading="deletingRoom === row.name" :disabled="!!deletingRoom || !!reassigningRoom">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <template #footer><el-button @click="showManageRooms = false">关闭</el-button></template>
    </el-dialog>

    <!-- Add Room Dialog -->
    <el-dialog v-model="showAddRoomDialog" title="新增鼠房" width="400px" append-to-body>
      <el-form label-width="80px">
        <el-form-item label="鼠房分类" required>
          <el-select v-model="newRoomCategory" style="width: 100%">
            <el-option v-for="category in roomCategories" :key="category" :label="category" :value="category" />
          </el-select>
        </el-form-item>
        <el-form-item label="鼠房名称" required>
          <el-input
            v-model="newRoomName"
            placeholder="如 东五302, 枫林实验楼"
            @keyup.enter="submitAddRoom"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRoomDialog = false">取消</el-button>
        <el-button type="primary" :loading="addingRoom" @click="submitAddRoom">确认新增</el-button>
      </template>
    </el-dialog>

    <!-- Mouse Detail Modal -->
    <MouseDetailModal
      v-model="showMouseDetailModal"
      :mouse-code="selectedMouseCode"
      :mouse-id="selectedMouseId"
      @set-owner="openSetOwnerFromDetail"
      @refresh="refreshAfterMouseUpdate"
    />
  </div>
</template>

<script setup>
import { ref, shallowRef, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { cagesApi, miceApi, importExportApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClaimerColors } from '@/composables/useClaimerColors'
import SetOwnerDialog from '@/components/SetOwnerDialog.vue'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import StrainSelect from '@/components/StrainSelect.vue'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'
import { Setting } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { getClaimerTagStyle, fetchClaimerColors } = useClaimerColors()

const loading = ref(false)
const exporting = ref(false)
const cagesList = shallowRef([])
const currentPage = ref(1)
const pageSize = 24
let cagesRequestId = 0
const roomOptions = ref([])
const activeRoom = ref('')
const activeCategory = ref('')
const cageNavigationStorageKey = 'mouse_lab_cage_navigation'
const savedRoomCategories = ref({})
const roomCategories = ['繁育鼠房', '临时鼠房', '实验鼠房']
function normalizeRoomCategory(category) {
  return category === '使用鼠房' ? '实验鼠房' : category
}
function roomCategory(room) {
  if (savedRoomCategories.value[room]) return normalizeRoomCategory(savedRoomCategories.value[room])
  if (/实验动物楼|江湾发育所/.test(room || '')) return '繁育鼠房'
  if (/东四/.test(room || '')) return '临时鼠房'
  return '实验鼠房'
}
const categoryRooms = computed(() => roomOptions.value.filter(room => !activeCategory.value || roomCategory(room) === activeCategory.value))
function changeCategory() {
  activeRoom.value = ''
  cageCodeFilter.value = ''
  loadCages()
}

function changeRoom() {
  cageCodeFilter.value = ''
  loadCages()
}
let roomsInitialized = false
const searchCode = ref('')
const onlyWithMice = ref(false)
const cageGenderFilter = ref('')
const cageCodeFilter = ref('')

function genderTagType(gender) {
  if (gender === 'M') return 'primary'
  if (gender === 'F') return 'danger'
  if (gender === 'M/F' || gender === '混合') return 'warning'
  return 'info'
}

function genderLabel(gender) {
  if (gender === 'M') return '♂ 雄'
  if (gender === 'F') return '♀ 雌'
  if (gender === 'M/F' || gender === '混合') return '♂♀ 混合'
  return '未知'
}

function mouseGenderItemClass(gender) {
  if (gender === 'M') return 'is-male'
  if (gender === 'F') return 'is-female'
  return 'is-unknown'
}

function cageMatchesGender(cage, gender) {
  if (gender === 'M/F') return cage?.gender === 'M/F' || cage?.gender === '混合'
  return cage?.gender === gender
}

const showSetOwnerDialog = ref(false)
const currentCageMice = ref([])

// Mouse Detail Modal
const showMouseDetailModal = ref(false)
const selectedMouseCode = ref('')
const selectedMouseId = ref(null)

function openMouseDetail(m) {
  selectedMouseCode.value = m.mouse_code
  selectedMouseId.value = m.id || null
  showMouseDetailModal.value = true
}

function openSetOwnerFromDetail(m) {
  currentCageMice.value = [m]
  showSetOwnerDialog.value = true
}

async function refreshAfterMouseUpdate() {
  await loadCages()
  if (!isEdit.value || !currentEditId.value) return
  try {
    const cage = await cagesApi.getCage(currentEditId.value)
    editingCageMice.value = cage.mice
    selectedEditingCageMice.value = []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '刷新笼位小鼠失败')
  }
}

const showCageDialog = ref(false)
const isEdit = ref(false)
const currentEditId = ref(null)
const editingCageMice = ref([])
const showLitterMiceDialog = ref(false)
const viewingLitterDate = ref('')
const viewingLitterMice = computed(() => editingCageMice.value.filter(mouse => mouse.dob === viewingLitterDate.value))
const editingCageRoom = ref('')
const editingCageCode = ref('')
const showAddCageMouse = ref(false)
const cageMouseBusy = ref(false)
const cageMouseForm = reactive({ add_count: 1, start_code: '', mouse_code: '', strain: '', gender: '未知', dob: '', parents: '', notes: '' })
const newLitterBirthDate = ref('')
const showMoveMouseDialog = ref(false)
const movingMouseBusy = ref(false)
const selectedEditingCageMice = ref([])
const showBatchEditMiceDialog = ref(false)
const batchEditBusy = ref(false)
const batchEditingMice = ref([])
const batchEditForm = reactive({ updateStrain: false, strain: '', updateDob: false, dob: '', updateGender: false, gender: '' })
const movingMice = ref([])
const targetCageOptions = ref([])
const moveMouseForm = reactive({ target_room: '', target_cage_code: '' })
const showSplitLitterDialog = ref(false)
const splitLitterBusy = ref(false)
const splitLitterDate = ref('')
const splitLitterRows = ref([])
const splitSelectedRows = ref([])
const splitTableRef = ref(null)
const splitTargetCages = ref([])
const splitBulkTarget = reactive({ room: '', cage_code: '' })

function cageLitterDates(cage) {
  const dates = Array.isArray(cage?.litter_birth_dates) ? cage.litter_birth_dates : []
  return [...new Set(dates.length ? dates : (cage?.litter_birth_date ? [cage.litter_birth_date] : []))].sort().reverse()
}

function normalizeCageDate(value) {
  const text = String(value || '').trim()
  let match = text.match(/^(\d{2}|\d{4})(\d{2})(\d{2})$/)
  if (!match) match = text.match(/^(\d{2}|\d{4})[年./-](\d{1,2})[月./-](\d{1,2})日?$/)
  if (!match) return ''
  const year = Number(match[1]) + (match[1].length === 2 ? 2000 : 0)
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() + 1 !== month || date.getDate() !== day) return ''
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function cageMatingDate(cage) {
  const direct = normalizeCageDate(cage?.mating_date)
  if (direct) return direct
  for (const value of [cage?.observation, cage?.notes]) {
    const match = String(value || '').match(/合笼(?:日期|时间)?\s*[：:]\s*(\d{6,8}|\d{2,4}[年./-]\d{1,2}[月./-]\d{1,2}日?)/)
    const parsed = normalizeCageDate(match?.[1])
    if (parsed) return parsed
  }
  return ''
}

function cageObservation(cage) {
  const observation = String(cage?.observation || '').trim()
  const notes = String(cage?.notes || '').trim()
  if (!notes || observation.includes(notes)) return observation
  return [observation, notes].filter(Boolean).join('\n')
}

function litterMouseCount(cage, birthDate) {
  return (cage?.mice || []).filter(mouse => mouse.dob === birthDate).length
}

function weaningDate(birthDate) {
  const date = new Date(`${birthDate}T00:00:00`)
  date.setDate(date.getDate() + 21)
  return date.toLocaleDateString('en-CA')
}

function isLitterDue(birthDate) {
  return weaningDate(birthDate) <= new Date().toLocaleDateString('en-CA')
}

function splitLitterButtonTitle(birthDate) {
  if (!isLitterDue(birthDate)) return `未满21天，${weaningDate(birthDate)} 起可批量换笼`
  if (!litterMouseCount({ mice: editingCageMice.value }, birthDate)) return '本笼没有出生日期与该批次一致的小鼠'
  return '将本批小鼠分别指定到不同笼位'
}

function openLitterMice(date) {
  viewingLitterDate.value = date
  showLitterMiceDialog.value = true
}

async function persistLitterDates(previousDates) {
  if (!isEdit.value) return true
  cageMouseBusy.value = true
  try {
    const cage = await cagesApi.updateCage(currentEditId.value, { litter_birth_dates: cageForm.litter_birth_dates })
    cageForm.litter_birth_dates = cageLitterDates(cage)
    await loadCages()
    window.dispatchEvent(new Event('todos-updated'))
    return true
  } catch (e) {
    cageForm.litter_birth_dates = previousDates
    ElMessage.error(e.response?.data?.detail || '保存生鼠批次失败')
    return false
  } finally {
    cageMouseBusy.value = false
  }
}

async function addLitterBatch() {
  const date = newLitterBirthDate.value
  if (!date) return
  if (cageForm.litter_birth_dates.includes(date)) return ElMessage.warning('这个生鼠日期已经记录')
  const previousDates = [...cageForm.litter_birth_dates]
  cageForm.litter_birth_dates = [...previousDates, date].sort().reverse()
  if (await persistLitterDates(previousDates)) {
    newLitterBirthDate.value = ''
    if (isEdit.value) {
      ElMessage.success('生鼠批次已新增，请录入本批小鼠')
      openAddCageMouse(date)
    } else {
      ElMessage.success('生鼠批次已添加，请先保存笼位后再新增本批小鼠')
    }
  }
}

async function removeLitterBatch(date) {
  const boundCount = litterMouseCount({ mice: editingCageMice.value }, date)
  if (boundCount) return ElMessage.warning(`该批次已绑定 ${boundCount} 只小鼠，请先修改这些小鼠的出生日期或移出本笼`)
  const previousDates = [...cageForm.litter_birth_dates]
  cageForm.litter_birth_dates = previousDates.filter(item => item !== date)
  if (await persistLitterDates(previousDates)) ElMessage.success(isEdit.value ? '生鼠批次已删除' : '已移除生鼠批次')
}

function openAddCageMouse(dob = '') {
  Object.assign(cageMouseForm, {
    add_count: 1, start_code: '', mouse_code: '', strain: cageForm.strain,
    gender: ['M', 'F'].includes(cageForm.gender) ? cageForm.gender : '未知',
    dob, parents: dob ? inferBreedingCageParents() : '', notes: ''
  })
  showAddCageMouse.value = true
}

function inferBreedingCageParents() {
  if (!['M/F', '混合'].includes(cageForm.gender)) return ''
  const litterDates = new Set(cageForm.litter_birth_dates)
  const candidates = editingCageMice.value.filter(mouse =>
    ['M', 'F'].includes(mouse.gender) && (!mouse.dob || !litterDates.has(mouse.dob))
  )
  const format = mouse => {
    const code = String(mouse.mouse_code || '').trim()
    return code && !code.toUpperCase().endsWith(mouse.gender) ? `${code}${mouse.gender}` : code
  }
  const males = candidates.filter(mouse => mouse.gender === 'M').map(format).filter(Boolean)
  const females = candidates.filter(mouse => mouse.gender === 'F').map(format).filter(Boolean)
  return [males.join('、'), females.join('、')].filter(Boolean).join('+')
}

function updateCageMouseCodes() {
  cageMouseForm.mouse_code = generateSequentialMouseCodes(cageMouseForm.start_code, cageMouseForm.add_count).join(', ')
}

async function addCageMouse() {
  if (cageMouseBusy.value || !isEdit.value || !authStore.isAdmin) return
  const codes = [...new Set(cageMouseForm.mouse_code.split(/[,，\s]+/).filter(Boolean))]
  if (!codes.length) return ElMessage.warning('请输入小鼠编号')
  cageMouseBusy.value = true
  try {
    const { add_count, start_code, mouse_code, ...sharedFields } = cageMouseForm
    const result = await miceApi.batchCreateMice({
      ...sharedFields, mouse_codes: codes, dob: cageMouseForm.dob || null,
      cage_code: editingCageCode.value, source_room: editingCageRoom.value, status: '在笼'
    })
    showAddCageMouse.value = false
    if (result.skipped_codes.length) ElMessage.warning(result.message)
    else ElMessage.success(result.message)
    const cage = await cagesApi.getCage(currentEditId.value)
    editingCageMice.value = cage.mice
    await loadCages()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '新增小鼠失败')
  } finally {
    cageMouseBusy.value = false
  }
}

async function removeCageMouse(mouse) {
  if (cageMouseBusy.value || !isEdit.value || !authStore.isAdmin) return
  cageMouseBusy.value = true
  try {
    await miceApi.batchUpdateStatus({ mouse_ids: [mouse.id], status: '出笼' })
    editingCageMice.value = editingCageMice.value.filter(item => item.id !== mouse.id)
    ElMessage.success('已移除鼠：笼位关联已清除，小鼠档案已保留')
    await loadCages()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '移除鼠失败')
  } finally {
    cageMouseBusy.value = false
  }
}

async function loadTargetCages(room) {
  if (!room) {
    targetCageOptions.value = []
    return
  }
  try {
    targetCageOptions.value = await cagesApi.listCages({ room })
  } catch (e) {
    targetCageOptions.value = []
    ElMessage.error(e.response?.data?.detail || '加载目标笼位失败')
  }
}

function splitCageOptions(room) {
  return splitTargetCages.value.filter(cage => cage.room === room && !(cage.room === editingCageRoom.value && cage.cage_code === editingCageCode.value))
}

async function openSplitLitterBatch(birthDate) {
  const mice = editingCageMice.value.filter(mouse => mouse.id && mouse.dob === birthDate)
  if (!mice.length) return ElMessage.warning('本笼没有可分笼的该批小鼠')
  splitLitterDate.value = birthDate
  splitLitterRows.value = mice.map(mouse => ({
    id: mouse.id,
    mouse_code: mouse.mouse_code,
    gender: mouse.gender,
    target_room: editingCageRoom.value,
    target_cage_code: '',
  }))
  splitSelectedRows.value = []
  Object.assign(splitBulkTarget, { room: editingCageRoom.value, cage_code: '' })
  try {
    splitTargetCages.value = await cagesApi.listCages()
    showSplitLitterDialog.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载目标笼位失败')
  }
}

function handleSplitSelection(rows) {
  splitSelectedRows.value = rows
}

function applySplitTarget() {
  if (!splitSelectedRows.value.length) return ElMessage.warning('请先勾选需要分到同一笼的小鼠')
  const room = splitBulkTarget.room?.trim()
  const cageCode = splitBulkTarget.cage_code?.trim()
  if (!room || !cageCode) return ElMessage.warning('请选择或输入目标鼠房和笼位')
  if (room === editingCageRoom.value && cageCode === editingCageCode.value) return ElMessage.warning('目标笼位不能与当前繁殖笼相同')
  for (const mouse of splitSelectedRows.value) {
    mouse.target_room = room
    mouse.target_cage_code = cageCode
  }
  splitTableRef.value?.clearSelection()
}

async function submitSplitLitterBatch() {
  if (splitLitterBusy.value) return
  const unassigned = splitLitterRows.value.filter(mouse => !mouse.target_room?.trim() || !mouse.target_cage_code?.trim())
  if (unassigned.length) return ElMessage.warning(`还有 ${unassigned.length} 只小鼠未指定目标笼位`)
  if (splitLitterRows.value.some(mouse => mouse.target_room.trim() === editingCageRoom.value && mouse.target_cage_code.trim() === editingCageCode.value)) {
    return ElMessage.warning('目标笼位不能与当前繁殖笼相同')
  }
  const grouped = new Map()
  for (const mouse of splitLitterRows.value) {
    const room = mouse.target_room.trim()
    const cageCode = mouse.target_cage_code.trim()
    const key = `${room}\u0000${cageCode}`
    if (!grouped.has(key)) grouped.set(key, { target_room: room, target_cage_code: cageCode, mouse_ids: [] })
    grouped.get(key).mouse_ids.push(mouse.id)
  }
  splitLitterBusy.value = true
  try {
    const result = await miceApi.batchSplitTransfer({ groups: [...grouped.values()], notes: `${splitLitterDate.value} 出生批次满21天批量换笼` })
    ElMessage.success(result.message)
    showSplitLitterDialog.value = false
    const cage = await cagesApi.getCage(currentEditId.value)
    editingCageMice.value = cage.mice
    selectedEditingCageMice.value = []
    await loadCages()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '批量换笼失败')
  } finally {
    splitLitterBusy.value = false
  }
}

function handleEditingCageSelection(mice) {
  selectedEditingCageMice.value = mice
}

function openBatchEditMice() {
  const mice = selectedEditingCageMice.value.filter(mouse => mouse?.id)
  if (!mice.length) return ElMessage.warning('请先选择需要编辑的小鼠')
  const first = mice[0]
  batchEditingMice.value = [...mice]
  Object.assign(batchEditForm, {
    updateStrain: false,
    strain: mice.every(mouse => (mouse.strain || '') === (first.strain || '')) ? (first.strain || '') : '',
    updateDob: false,
    dob: mice.every(mouse => (mouse.dob || '') === (first.dob || '')) ? (first.dob || '') : '',
    updateGender: false,
    gender: mice.every(mouse => (mouse.gender || '') === (first.gender || '')) ? (first.gender || '') : ''
  })
  showBatchEditMiceDialog.value = true
}

async function submitBatchEditMice() {
  if (batchEditBusy.value) return
  if (!batchEditForm.updateStrain && !batchEditForm.updateDob && !batchEditForm.updateGender) return ElMessage.warning('请至少勾选一个要修改的字段')
  if (batchEditForm.updateGender && !batchEditForm.gender) return ElMessage.warning('请选择性别')

  const payload = { mouse_ids: batchEditingMice.value.map(mouse => mouse.id) }
  if (batchEditForm.updateStrain) payload.strain = (batchEditForm.strain || '').trim()
  if (batchEditForm.updateDob) payload.dob = batchEditForm.dob || null
  if (batchEditForm.updateGender) payload.gender = batchEditForm.gender
  batchEditBusy.value = true
  try {
    const result = await miceApi.batchUpdateFields(payload)
    if (batchEditForm.updateStrain && !cageForm.strain && payload.strain) {
      cageForm.strain = payload.strain
    }
    showBatchEditMiceDialog.value = false
    ElMessage.success(result.message || `成功批量更新 ${batchEditingMice.value.length} 只小鼠`)
    await refreshAfterMouseUpdate()
    window.dispatchEvent(new Event('todos-updated'))
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '批量编辑小鼠失败')
  } finally {
    batchEditBusy.value = false
  }
}

function openMoveMice(mice) {
  const validMice = mice.filter(mouse => mouse?.id)
  if (!validMice.length) return ElMessage.warning('请先选择需要换笼的小鼠')
  movingMice.value = [...validMice]
  Object.assign(moveMouseForm, {
    target_room: editingCageRoom.value,
    target_cage_code: ''
  })
  loadTargetCages(moveMouseForm.target_room)
  showMoveMouseDialog.value = true
}

function openMoveMouse(mouse) {
  openMoveMice([mouse])
}

function openBatchMoveMice() {
  openMoveMice(selectedEditingCageMice.value)
}

function handleMoveRoomChange(room) {
  moveMouseForm.target_cage_code = ''
  loadTargetCages(room)
}

async function submitMoveMouse() {
  if (!movingMice.value.length || movingMouseBusy.value || !authStore.isAdmin) return
  const targetRoom = moveMouseForm.target_room.trim()
  const targetCageCode = moveMouseForm.target_cage_code.trim()
  if (!targetRoom || !targetCageCode) {
    ElMessage.warning('请选择目标鼠房和笼位')
    return
  }
  if (targetRoom === editingCageRoom.value && targetCageCode === editingCageCode.value.trim()) {
    ElMessage.warning('目标笼位不能与当前笼位相同')
    return
  }

  movingMouseBusy.value = true
  try {
    const movingIds = new Set(movingMice.value.map(mouse => mouse.id))
    const result = await miceApi.batchTransfer({
      mouse_ids: [...movingIds],
      target_room: targetRoom,
      target_cage_code: targetCageCode
    })
    editingCageMice.value = editingCageMice.value.filter(item => !movingIds.has(item.id))
    selectedEditingCageMice.value = []
    showMoveMouseDialog.value = false
    ElMessage.success(result.message || '换笼成功，已写入流转日志')
    await loadCages()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '换笼失败')
  } finally {
    movingMouseBusy.value = false
  }
}

const cageForm = reactive({
  room: '',
  cage_code: '',
  strain: '',
  gender: 'M',
  capacity: 5,
  mating_date: '',
  litter_birth_dates: [],
  observation: '',
  notes: ''
})

const cageSaving = ref(false)
const parsedNewCageCodes = computed(() => [...new Set(String(cageForm.cage_code || '')
  .split(/[,，、\s]+/)
  .map(code => code.trim())
  .filter(Boolean))])

const filteredCages = computed(() => {
  return cagesList.value.filter(c => {
    if (activeCategory.value && roomCategory(c.room) !== activeCategory.value) return false
    if (activeRoom.value && c.room !== activeRoom.value) return false
    if (onlyWithMice.value && c.mouse_count === 0) return false
    if (cageCodeFilter.value && c.cage_code !== cageCodeFilter.value) return false
    if (cageGenderFilter.value && !cageMatchesGender(c, cageGenderFilter.value)) return false
    if (searchCode.value) {
      const q = searchCode.value.toLowerCase()
      const codeMatch = (c.cage_code || '').toLowerCase().includes(q)
      const strainMatch = (c.strain || '').toLowerCase().includes(q)
      const miceMatch = (c.mice || []).some(m => (m.mouse_code || '').toLowerCase().includes(q) || (m.owner_name || '').includes(q))
      if (!codeMatch && !strainMatch && !miceMatch) return false
    }
    return true
  })
})

const cageCodeOptions = computed(() => [...new Set(cagesList.value
  .filter(cage => (!activeCategory.value || roomCategory(cage.room) === activeCategory.value)
    && (!activeRoom.value || cage.room === activeRoom.value))
  .map(cage => cage.cage_code)
  .filter(Boolean))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })))

const pagedCages = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredCages.value.slice(start, start + pageSize)
})

watch([activeCategory, activeRoom, searchCode, onlyWithMice, cageGenderFilter, cageCodeFilter], () => {
  currentPage.value = 1
}, { flush: 'sync' })

watch([activeCategory, activeRoom, cageGenderFilter, cageCodeFilter], ([category, room, gender, cageCode]) => {
  localStorage.setItem(cageNavigationStorageKey, JSON.stringify({ category, room, gender, cageCode }))
})

watch(() => filteredCages.value.length, (total) => {
  currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(total / pageSize)))
})

async function loadRooms() {
  try {
    const rooms = await cagesApi.listRooms({ include_categories: true })
    roomOptions.value = rooms.map(room => room.name)
    savedRoomCategories.value = Object.fromEntries(rooms.map(room => [room.name, normalizeRoomCategory(room.category)]))
    if (!roomsInitialized) {
      if (route.query.room) {
        activeRoom.value = String(route.query.room)
        activeCategory.value = roomCategory(activeRoom.value)
      } else {
        try {
          const saved = JSON.parse(localStorage.getItem(cageNavigationStorageKey) || '{}')
          if (roomCategories.includes(saved.category)) activeCategory.value = saved.category
          if (roomOptions.value.includes(saved.room) && (!activeCategory.value || roomCategory(saved.room) === activeCategory.value)) {
            activeRoom.value = saved.room
          }
          if (['M', 'F', 'M/F'].includes(saved.gender)) cageGenderFilter.value = saved.gender
          if (typeof saved.cageCode === 'string') cageCodeFilter.value = saved.cageCode
        } catch {
          localStorage.removeItem(cageNavigationStorageKey)
        }
      }
      roomsInitialized = true
    } else if (activeRoom.value && !roomOptions.value.includes(activeRoom.value)) {
      activeRoom.value = ''
    }
  } catch (e) {
    console.error(e)
  }
}

const showAddRoomDialog = ref(false)
const showManageRooms = ref(false)
const managedRooms = ref([])
const managedRoomTree = computed(() => roomCategories.map(category => {
  const children = managedRooms.value
    .filter(room => room.category === category)
    .map(room => ({ ...room, treeKey: `room:${room.name}` }))
  return {
    treeKey: `category:${category}`, name: category, isCategory: true, children,
    cage_count: children.reduce((total, room) => total + (room.cage_count || 0), 0),
    mouse_count: children.reduce((total, room) => total + (room.mouse_count || 0), 0)
  }
}))
const managingRoomsLoading = ref(false)
const deletingRoom = ref('')
const draggedRoom = ref(null)
const dragTargetCategory = ref('')
const reassigningRoom = ref('')

async function openManageRooms() {
  showManageRooms.value = true
  managingRoomsLoading.value = true
  try {
    managedRooms.value = await cagesApi.listRooms({ include_categories: true })
  } catch (e) {
    ElMessage.error('加载鼠房列表失败')
  } finally {
    managingRoomsLoading.value = false
  }
}

function startRoomDrag(room, event) {
  if (reassigningRoom.value) {
    event.preventDefault()
    return
  }
  draggedRoom.value = room
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', room.name)
}

function handleRoomDragOver(category, event) {
  if (!draggedRoom.value || reassigningRoom.value) return
  dragTargetCategory.value = category
  if (event?.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function finishRoomDrag() {
  draggedRoom.value = null
  dragTargetCategory.value = ''
}

async function dropRoomIntoCategory(category) {
  const room = draggedRoom.value
  finishRoomDrag()
  if (!room || reassigningRoom.value || room.category === category) return

  const previousCategory = room.category
  managedRooms.value = managedRooms.value.map(item => item.name === room.name
    ? { ...item, category }
    : item)
  reassigningRoom.value = room.name
  try {
    await cagesApi.createRoom({ name: room.name, category })
    savedRoomCategories.value = { ...savedRoomCategories.value, [room.name]: category }
    if (activeRoom.value === room.name) activeCategory.value = category
    await loadRooms()
    await loadCages()
    ElMessage.success(`已将 ${room.name} 移至${category}`)
  } catch (e) {
    managedRooms.value = managedRooms.value.map(item => item.name === room.name
      ? { ...item, category: previousCategory }
      : item)
    ElMessage.error(e.response?.data?.detail || '调整鼠房分类失败')
  } finally {
    reassigningRoom.value = ''
  }
}

async function deleteManagedRoom(room) {
  if (deletingRoom.value) return
  deletingRoom.value = room.name
  try {
    const result = await cagesApi.deleteRoom(room.name)
    ElMessage.success(result.message)
    managedRooms.value = managedRooms.value.filter(item => item.name !== room.name)
    if (activeRoom.value === room.name) activeRoom.value = ''
    await loadRooms()
    await loadCages()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除鼠房失败')
  } finally {
    deletingRoom.value = ''
  }
}
const newRoomName = ref('')
const newRoomCategory = ref('实验鼠房')
const addingRoom = ref(false)

function openAddRoomDialog() {
  newRoomName.value = ''
  newRoomCategory.value = activeCategory.value || '实验鼠房'
  showAddRoomDialog.value = true
}

async function submitAddRoom() {
  const name = newRoomName.value.trim()
  if (!name) {
    ElMessage.warning('请输入鼠房名称')
    return
  }
  addingRoom.value = true
  try {
    const res = await cagesApi.createRoom({ name, category: newRoomCategory.value })
    ElMessage.success(res.message || '成功新增鼠房')
    showAddRoomDialog.value = false
    await loadRooms()
    if (showManageRooms.value) await openManageRooms()
    activeRoom.value = name
    activeCategory.value = roomCategory(name)
    loadCages()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '新增鼠房失败')
  } finally {
    addingRoom.value = false
  }
}

async function loadCages() {
  const requestId = ++cagesRequestId
  loading.value = true
  try {
    const params = {}
    if (activeRoom.value) params.room = activeRoom.value
    const cages = await cagesApi.listCages(params)
    if (requestId === cagesRequestId) cagesList.value = cages
  } catch (e) {
    if (requestId === cagesRequestId) ElMessage.error('加载笼位失败')
  } finally {
    if (requestId === cagesRequestId) loading.value = false
  }
}

function openSetOwnerForCage(cage) {
  if (!authStore.isAdmin) {
    ElMessage.warning('需管理员登录后操作')
    return
  }
  currentCageMice.value = [...cage.mice]
  showSetOwnerDialog.value = true
}

function onSetOwnerSuccess() {
  loadCages()
}

function openAddCageDialog() {
  isEdit.value = false
  currentEditId.value = null
  newLitterBirthDate.value = ''
  Object.assign(cageForm, {
    room: activeRoom.value || roomOptions.value[0] || '默认鼠房',
    cage_code: '',
    strain: '',
    gender: 'M',
    capacity: 5,
    mating_date: '',
    litter_birth_dates: [],
    observation: '',
    notes: ''
  })
  showCageDialog.value = true
}

function openEditCageDialog(cage) {
  isEdit.value = true
  currentEditId.value = cage.id
  editingCageMice.value = [...cage.mice]
  editingCageRoom.value = cage.room
  editingCageCode.value = cage.cage_code
  selectedEditingCageMice.value = []
  movingMice.value = []
  showAddCageMouse.value = false
  newLitterBirthDate.value = ''
  Object.assign(cageForm, {
    room: cage.room,
    cage_code: cage.cage_code,
    strain: cage.strain,
    gender: cage.gender,
    capacity: cage.capacity,
    mating_date: cageMatingDate(cage),
    litter_birth_dates: cageLitterDates(cage),
    observation: cageObservation(cage),
    notes: cage.notes || ''
  })
  showCageDialog.value = true
}

async function submitCageForm() {
  const newCageCodes = parsedNewCageCodes.value
  if (isEdit.value ? !cageForm.cage_code.trim() : newCageCodes.length === 0) {
    ElMessage.warning('请输入笼位编号')
    return
  }
  cageSaving.value = true
  try {
    if (isEdit.value) {
      try {
        await cagesApi.updateCage(currentEditId.value, cageForm)
        ElMessage.success('笼位已更新')
      } catch (e) {
        const detail = e.response?.data?.detail
        if (e.response?.status !== 409 || typeof detail !== 'string' || !detail.includes('确认合并')) throw e
        try {
          await ElMessageBox.confirm(detail, '合并笼位确认', {
            confirmButtonText: '确认合并',
            cancelButtonText: '取消',
            type: 'warning',
          })
        } catch {
          return
        }
        await cagesApi.updateCage(currentEditId.value, { ...cageForm, merge_existing: true })
        ElMessage.success('笼位已合并，两笼小鼠已归入目标笼位，原笼位已保留为空笼')
      }
    } else {
      const { cage_code, ...sharedFields } = cageForm
      const result = await cagesApi.batchCreateCages({ ...sharedFields, cage_codes: newCageCodes })
      ElMessage.success(result.message || `成功新增 ${newCageCodes.length} 个笼位`)
    }
    showCageDialog.value = false
    loadCages()
    loadRooms()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    cageSaving.value = false
  }
}

async function handleDeleteCage(id) {
  try {
    await cagesApi.deleteCage(id)
    ElMessage.success('笼位已删除')
    loadCages()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    await importExportApi.exportCages()
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  fetchClaimerColors()
  await loadRooms()
  await loadCages()
  const requestedId = Number(route.query.edit_cage_id)
  if (requestedId) {
    try {
      const cage = cagesList.value.find(item => item.id === requestedId) || await cagesApi.getCage(requestedId)
      openEditCageDialog(cage)
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '待办关联的笼位不存在')
    } finally {
      const query = { ...route.query }
      delete query.edit_cage_id
      router.replace({ path: route.path, query })
    }
  }
})
</script>

<style scoped>
.room-category-count {
  display: inline-block;
  margin-left: 24px;
}

.room-category-drop-target {
  display: inline-flex;
  align-items: center;
  width: calc(100% - 28px);
  min-height: 34px;
  margin: -5px -8px -5px 0;
  padding: 5px 8px;
  border: 1px dashed transparent;
  border-radius: 7px;
  vertical-align: middle;
  transition: color 0.15s, background-color 0.15s, border-color 0.15s;
}

.room-category-drop-target.is-drag-over {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
}

.room-drop-hint {
  margin-left: auto;
  color: var(--el-color-primary);
}

.managed-room-drag-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  vertical-align: middle;
  cursor: grab;
  user-select: none;
}

.managed-room-drag-item:active {
  cursor: grabbing;
}

.managed-room-drag-item.is-dragging {
  opacity: 0.45;
}

.room-drag-handle {
  color: var(--el-text-color-placeholder);
  font-weight: 700;
  letter-spacing: -4px;
}

.room-settings-button {
  margin-left: auto;
}

.cage-card {
  transition: transform 0.15s, box-shadow 0.15s;
}
.cage-card:hover {
  transform: translateY(-2px);
}

.mouse-item.is-male {
  background-color: #eff6ff;
  border-color: #bfdbfe;
}

.mouse-item.is-female {
  background-color: #fdf2f8;
  border-color: #fbcfe8;
}

.mouse-item.is-unknown {
  background-color: #f9fafb;
}

.male-symbol {
  color: #2563eb !important;
  font-weight: 700;
}

.female-symbol {
  color: #ec4899 !important;
  font-weight: 700;
}

.litter-batches {
  width: 100%;
}

.litter-add-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.litter-batch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.litter-batch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid #e9d5ff;
  border-radius: 8px;
  background: #faf5ff;
}

.split-bulk-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #eff6ff;
}

.batch-edit-form :deep(.el-form-item__label) {
  justify-content: flex-start;
}

@media (max-width: 1023px) {
  .cages-page .cage-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
  .cage-card { min-width: 0; }
  .mouse-item { flex-wrap: wrap; gap: 6px; padding: 8px; }
  .mouse-summary { flex-wrap: wrap; min-width: 0; overflow-wrap: anywhere; }
  .mouse-age { white-space: nowrap; }
  .mouse-owner { max-width: 100%; margin-left: auto; }
  .mouse-owner :deep(.el-tag) { height: auto; min-height: 24px; white-space: normal; overflow-wrap: anywhere; max-width: 100%; }
  .cage-card :deep(.justify-between) { flex-wrap: wrap; gap: 8px; }
}
@media (max-width: 767px) {
  .litter-add-row, .litter-batch-item, .split-bulk-bar { align-items: stretch; flex-direction: column; }
  .cages-page .cage-grid { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  .cage-card { padding: 14px; }
  .mice-chips { max-height: none; }
  .mouse-item { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; }
  .mouse-owner { max-width: 140px; }
  .cage-card :deep(.el-button) { min-height: 36px; }
  .cages-page :deep(.el-radio-group) { max-width: 100%; flex-wrap: wrap; gap: 6px; }
  .cages-page :deep(.el-radio-button__inner) { border-radius: 6px; border: 1px solid var(--el-border-color); }
}
</style>
