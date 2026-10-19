// Install the isolated runner: pnpm --dir build/inline-edit-ui add playwright
// Build first, start the app, then run: node scripts/test-grid-edit-ui.mjs
// Every API request is intercepted; these checks never write to the real database.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const require = createRequire(new URL('../build/inline-edit-ui/package.json', import.meta.url))
const { chromium } = require('playwright')
const baseURL = process.env.UI_TEST_BASE_URL || 'http://127.0.0.1:8000'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 2200, height: 1000 } })
const errors = []
const writes = []
let rejectNextGenotypeSave = false
const user = { id: 1, role: 'admin', username: 'ui-test', display_name: '交互测试', is_authenticated: true }
const mice = [1, 2, 3].map(id => ({
  id, mouse_code: `UI00${id}`, strain: '5xFAD', gender: 'F', dob: null,
  parents: '', status: '在笼', cage_id: null, age_weeks: null, genotypes: [],
  notes: '原备注', claim_purpose: '', owner_name: null,
}))
const records = mice.map(mouse => ({ ...mouse, mouse_id: mouse.id, test_date: null, genotype_1: null }))

await context.addInitScript(user => {
  localStorage.setItem('mouse_lab_token', 'ui-test-only')
  localStorage.setItem('mouse_lab_user', JSON.stringify(user))
}, user)
await context.route('**/api/**', async route => {
  const request = route.request()
  const path = new URL(request.url()).pathname
  let json = []
  if (path === '/api/auth/me') json = user
  else if (path === '/api/settings/public') json = { system_name: '交互测试', transfer_rooms: [] }
  else if (path === '/api/mice/batch-update-fields') {
    const { mouse_ids, ...values } = request.postDataJSON()
    writes.push({ path, mouse_ids, ...values })
    const items = mice.filter(mouse => mouse_ids.includes(mouse.id))
    items.forEach(mouse => Object.assign(mouse, values))
    json = { affected_count: items.length, items }
  } else if (path === '/api/genotypes/batch-fill') {
    const data = request.postDataJSON()
    writes.push({ path, ...data })
    if (rejectNextGenotypeSave) {
      rejectNextGenotypeSave = false
      return route.fulfill({ status: 422, json: { detail: [{ loc: ['body', 'field'], type: 'literal_error', msg: 'Input should be genotype_1, genotype_2 or genotype_3' }] } })
    }
    const items = records.filter(record => data.record_ids.includes(record.id))
    items.forEach(record => { record[data.field] = data.value || null })
    json = { updated: items.length, items }
  } else if (path === '/api/genotypes/filter-options') json = { genotype_1: ['HET'], genotype_2: [], genotype_3: [] }
  else if (path === '/api/genotypes') json = { total: records.length, items: records }
  else if (path === '/api/mice') json = { total: mice.length, items: mice }
  else if (path === '/api/mice/all-strains') json = ['5xFAD', 'C57BL/6J']
  else if (path === '/api/mouse-statuses') json = [{ name: '在笼' }, { name: '实验中' }, { name: '死亡', removes_from_cage: true }]
  else if (path === '/api/claimers' || path === '/api/members') json = [{ id: 1, name: '领取人甲' }]
  // Unknown APIs stay mocked too, including dialogs and notifications.
  return route.fulfill({ json })
})

const page = await context.newPage()
page.setDefaultTimeout(10000)
page.on('pageerror', error => errors.push(error.message))

async function cell(code, label) {
  const table = page.locator('.el-table').first()
  const headers = await table.locator('.el-table__header-wrapper th').allTextContents()
  const index = headers.findIndex(text => text.trim() === label)
  assert.ok(index >= 0, `Missing column: ${label}`)
  return table.locator('.el-table__body-wrapper .el-table__row').filter({ hasText: code }).first().locator('td').nth(index).locator('.genotype-grid-cell')
}

async function saved(action) {
  const response = page.waitForResponse(response => /batch-(update-fields|fill)$/.test(new URL(response.url()).pathname))
  await action()
  await response
  await page.locator('.el-loading-mask').waitFor({ state: 'hidden' })
}

async function dragFill(source, target, cancel = false) {
  const handle = source.locator('.genotype-fill-handle')
  await handle.scrollIntoViewIfNeeded()
  const from = await handle.boundingBox()
  const to = await target.boundingBox()
  assert.ok(from && to)
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 12 })
  if (cancel) await page.keyboard.press('Escape')
  await page.mouse.up()
}

try {
  await page.goto(`${baseURL}/mice`)
  console.log('Checking mouse cells')
  await page.getByText('UI001', { exact: true }).first().waitFor()
  const strain = await cell('UI001', '品系 / 基因型')
  await strain.locator('span').first().click()
  await strain.locator('input').fill('C57BL/6J')
  await saved(() => strain.locator('input').press('Enter'))
  assert.equal(writes.at(-1).strain, 'C57BL/6J')
  await saved(async () => dragFill(strain, await cell('UI003', '品系 / 基因型')))
  console.log('Mouse text editing and fill passed')
  assert.deepEqual(writes.at(-1).mouse_ids, [2, 3])
  assert.equal(writes.at(-1).strain, 'C57BL/6J')
  const count = writes.length
  await dragFill(strain, await cell('UI003', '品系 / 基因型'), true)
  assert.equal(writes.length, count)

  const gender = await cell('UI001', '性别')
  await gender.click()
  await saved(() => page.getByRole('option', { name: '♂ 雄', exact: true }).click())
  assert.equal(writes.at(-1).gender, 'M')
  const dob = await cell('UI001', '出生日期 / 周龄')
  console.log('Mouse gender passed; checking calendar')
  await dob.click()
  await page.locator('.el-picker-panel:visible').waitFor()
  await saved(() => page.locator('.el-date-table td.available:not(.prev-month):not(.next-month)').filter({ hasText: /^15$/ }).click())
  assert.match(writes.at(-1).dob, /^\d{4}-\d{2}-15$/)
  await saved(async () => dragFill(dob, await cell('UI003', '出生日期 / 周龄')))
  assert.deepEqual(writes.at(-1).mouse_ids, [2, 3])
  await dob.click()
  await dob.locator('input').fill('2026-08-03')
  await saved(() => page.locator('.app-header').click())
  assert.equal(writes.at(-1).dob, '2026-08-03')
  await dob.click()
  await dob.locator('input').fill('')
  await saved(() => page.locator('.app-header').click())
  assert.equal(writes.at(-1).dob, null)

  const parents = await cell('UI001', '父母系谱 (M+F)')
  await parents.getByRole('button', { name: '编辑父母系谱 (M+F)', exact: true }).click()
  await parents.locator('input').fill('P001M+P002F')
  await saved(() => parents.locator('input').press('Enter'))
  assert.equal(writes.at(-1).parents, 'P001M+P002F')

  const owner = await cell('UI001', '当前领取人')
  await owner.click()
  await saved(() => page.getByRole('option', { name: '领取人甲', exact: true }).click())
  assert.equal(writes.at(-1).owner_name, '领取人甲')
  const status = await cell('UI001', '状态')
  await status.click()
  await saved(() => page.getByRole('option', { name: '实验中', exact: true }).click())
  assert.equal(writes.at(-1).status, '实验中')
  const notes = await cell('UI001', '备注')
  await notes.click()
  await notes.locator('input').fill('已更新备注')
  await saved(() => notes.locator('input').press('Enter'))
  assert.equal(writes.at(-1).notes, '已更新备注')
  const beforeCancel = writes.length
  await notes.click()
  await notes.locator('input').fill('不应保存')
  await notes.locator('input').press('Escape')
  assert.equal(writes.length, beforeCancel)
  assert.equal((await notes.textContent()).trim(), '已更新备注')
  const purpose = await cell('UI001', '领用用途')
  await purpose.click()
  await purpose.locator('input').fill('成像实验')
  await saved(() => purpose.locator('input').press('Enter'))
  assert.equal(writes.at(-1).claim_purpose, '成像实验')
  await page.screenshot({ path: fileURLToPath(new URL('../build/inline-edit-ui/mice.png', import.meta.url)), fullPage: true })

  await page.goto(`${baseURL}/genotypes`)
  console.log('Mouse fields passed; checking genotype cells')
  await page.getByText('UI001', { exact: true }).first().waitFor()
  const genotypeDob = await cell('UI001', '出生日期')
  await genotypeDob.dblclick()
  await page.locator('.el-picker-panel:visible').waitFor()
  await saved(() => page.locator('.el-date-table td.available:not(.prev-month):not(.next-month)').filter({ hasText: /^16$/ }).click())
  assert.equal(writes.at(-1).field, 'dob')
  assert.match(writes.at(-1).value, /^\d{4}-\d{2}-16$/)
  await saved(async () => dragFill(genotypeDob, await cell('UI003', '出生日期')))
  assert.deepEqual(writes.at(-1).record_ids, [2, 3])

  const genotypeGender = await cell('UI001', '性别')
  await genotypeGender.dblclick()
  await saved(() => page.getByRole('option', { name: '♂ 雄', exact: true }).click())
  assert.equal(writes.at(-1).field, 'gender')
  assert.equal(writes.at(-1).value, 'M')
  rejectNextGenotypeSave = true
  await genotypeDob.dblclick()
  await saved(() => page.locator('.el-date-table td.available:not(.prev-month):not(.next-month)').filter({ hasText: /^17$/ }).click())
  await page.getByText('后端尚未支持此列，请重启后端服务后重试', { exact: true }).waitFor()
  assert.deepEqual(errors, [])

  await mkdir(new URL('../build/inline-edit-ui/', import.meta.url), { recursive: true })
  await page.screenshot({ path: fileURLToPath(new URL('../build/inline-edit-ui/genotypes.png', import.meta.url)), fullPage: true })
  console.log('PASS: single-click editing, dropdowns, calendar selection, drag fill, Escape cancellation, genotype saves, and old-backend errors. All APIs mocked.')
} catch (error) {
  await page.screenshot({ path: fileURLToPath(new URL('../build/inline-edit-ui/failure.png', import.meta.url)), fullPage: true })
  console.error('Writes before failure:', writes)
  throw error
} finally {
  await browser.close()
}
