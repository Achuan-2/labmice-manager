// FastAPI returns either a message or a list of field validation errors.
export function apiErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return fallback
  if (detail.some(item => item.loc?.includes('field') && item.type === 'literal_error')) {
    return '后端尚未支持此列，请重启后端服务后重试'
  }
  return detail.map(item => item.msg?.replace(/^Value error, /, '')).filter(Boolean).join('；') || fallback
}
