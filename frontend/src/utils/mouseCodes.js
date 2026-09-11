export function generateSequentialMouseCodes(startCode, count) {
  const normalizedCode = String(startCode || '').trim()
  const normalizedCount = Number(count)
  const match = normalizedCode.match(/^(.*?)(\d+)$/)

  if (!match || !Number.isInteger(normalizedCount) || normalizedCount < 1) return []

  const [, prefix, numericPart] = match
  const startNumber = Number(numericPart)
  const width = numericPart.length

  return Array.from({ length: normalizedCount }, (_, index) => {
    const nextNumber = String(startNumber + index).padStart(width, '0')
    return `${prefix}${nextNumber}`
  })
}
