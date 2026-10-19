export function isClaimedOutOfCage(mouse) {
  return Boolean(mouse && !mouse.cage_id && !mouse.cage_code)
}

export function mouseStatusLabel(mouse) {
  return mouse?.status || (isClaimedOutOfCage(mouse) ? '出笼' : '在笼')
}

const pendingGenotypeValues = new Set(['', '/', '-', '无', 'None', 'nan', '待检验', '待鉴定', '待测', '未测', '未鉴定'])

export function hasGenotypeResult(record) {
  return ['genotype_1', 'genotype_2', 'genotype_3'].some(
    field => !pendingGenotypeValues.has(String(record?.[field] ?? '').trim())
  )
}
