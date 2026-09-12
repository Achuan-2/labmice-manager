import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// Request Interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('mouse_lab_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response Interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // If 401 unauthorized, user needs to login
    if (error.response?.status === 401) {
      localStorage.removeItem('mouse_lab_token')
      localStorage.removeItem('mouse_lab_user')
      window.dispatchEvent(new Event('auth-unauthorized'))
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: (data) => api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
  listAdmins: () => api.get('/auth/admins'),
  createAdmin: (data) => api.post('/auth/admins', data),
  updateAdminDisplayName: (id, data) => api.put(`/auth/admins/${id}/display-name`, data),
  updateAdminPassword: (id, data) => api.put(`/auth/admins/${id}/password`, data),
  deleteAdmin: (id) => api.delete(`/auth/admins/${id}`),
}

export const settingsApi = {
  getPublic: () => api.get('/settings/public'),
  update: (data) => api.put('/settings', data),
  addTransferRoom: (data) => api.post('/settings/transfer-rooms', data),
  renameTransferRoom: (oldName, data) => api.put(`/settings/transfer-rooms/${encodeURIComponent(oldName)}`, data),
  deleteTransferRoom: (name) => api.delete(`/settings/transfer-rooms/${encodeURIComponent(name)}`),
}

export const miceApi = {
  listMice: (params) => api.get('/mice', { params }),
  getMouse: (id) => api.get(`/mice/${id}`),
  getMouseByCode: (code) => api.get(`/mice/by-code/${encodeURIComponent(code)}`),
  createMouse: (data) => api.post('/mice', data),
  batchCreateMice: (data) => api.post('/mice/batch-create', data),
  updateMouse: (id, data) => api.put(`/mice/${id}`, data),
  deleteMouse: (id) => api.delete(`/mice/${id}`),
  batchSetOwner: (data) => api.post('/mice/batch-set-owner', data),
  batchTransfer: (data) => api.post('/mice/batch-transfer', data),
  batchSplitTransfer: (data) => api.post('/mice/batch-split-transfer', data),
  batchUpdateStatus: (data) => api.post('/mice/batch-update-status', data),
  batchUpdateFields: (data) => api.post('/mice/batch-update-fields', data),
  getAllStrains: () => api.get('/mice/all-strains'),
  getAllParents: () => api.get('/mice/all-parents'),
  parseParents: (parents) => api.post('/mice/parse-parents', { parents }),
}

export const mouseStatusesApi = {
  listStatuses: () => api.get('/mouse-statuses'),
  createStatus: (data) => api.post('/mouse-statuses', data),
  renameStatus: (id, data) => api.put(`/mouse-statuses/${id}`, data),
  deleteStatus: (id, replacementStatus = null) => api.delete(`/mouse-statuses/${id}`, {
    data: { replacement_status: replacementStatus }
  }),
}

export const cagesApi = {
  listCages: (params) => api.get('/cages', { params }),
  listRooms: (params) => api.get('/cages/rooms', { params }),
  createRoom: (data) => api.post('/cages/rooms', data),
  deleteRoom: (name) => api.delete(`/cages/rooms/${encodeURIComponent(name)}`),
  getCage: (id) => api.get(`/cages/${id}`),
  createCage: (data) => api.post('/cages', data),
  batchCreateCages: (data) => api.post('/cages/batch', data),
  updateCage: (id, data) => api.put(`/cages/${id}`, data),
  deleteCage: (id) => api.delete(`/cages/${id}`),
}

export const membersApi = {
  listMembers: () => api.get('/members'),
  getMemberMice: (id) => api.get(`/members/${id}/mice`),
  createMember: (data) => api.post('/members', data),
  updateMember: (id, data) => api.put(`/members/${id}`, data),
  deleteMember: (id) => api.delete(`/members/${id}`),
}

export const claimersApi = {
  listClaimers: () => api.get('/members'),
  getClaimerMice: (id) => api.get(`/members/${id}/mice`),
  createClaimer: (data) => api.post('/members', data),
  updateClaimer: (id, data) => api.put(`/members/${id}`, data),
  deleteClaimer: (id) => api.delete(`/members/${id}`),
}

export const transferRequestsApi = {
  getAssignedMice: (id) => api.get(`/transfer-requests/${id}/assigned-mice`),
  listRequests: (params) => api.get('/transfer-requests', { params }),
  createRequest: (data) => api.post('/transfer-requests', data),
  processRequest: (id, data) => api.put(`/transfer-requests/${id}`, data),
  deleteRequest: (id) => api.delete(`/transfer-requests/${id}`),
}

export const genotypesApi = {
  listGenotypes: (params) => api.get('/genotypes', { params }),
  getByMouse: (mouseCode) => api.get(`/genotypes/by-mouse/${mouseCode}`),
  createGenotype: (data) => api.post('/genotypes', data),
  createGenotypes: (data) => api.post('/genotypes/batch', data),
  updateGenotype: (id, data) => api.put(`/genotypes/${id}`, data),
  deleteGenotype: (id) => api.delete(`/genotypes/${id}`),
}

export const transfersApi = {
  listTransfers: (params) => api.get('/transfers', { params }),
}

export const primersApi = {
  listPrimers: (params) => api.get('/primers', { params }),
  createPrimer: (data) => api.post('/primers', data),
  updatePrimer: (id, data) => api.put(`/primers/${id}`, data),
  deletePrimer: (id) => api.delete(`/primers/${id}`),
}

export const strainsApi = {
  listStrains: () => api.get('/strains'),
  getStrain: (name) => api.get(`/strains/${encodeURIComponent(name)}`),
  createOrUpdateStrain: (data) => api.post('/strains', data),
  updateStrainNotes: (name, notes) => api.put(`/strains/${encodeURIComponent(name)}`, { notes }),
  syncAndMerge: () => api.post('/strains/sync/merge-cases'),
}

export const statsApi = {
  getDashboardStats: () => api.get('/stats/dashboard'),
}

export const todosApi = {
  listTodos: (params) => api.get('/todos', { params }),
  createTodo: (data) => api.post('/todos', data),
  updateTodo: (id, data) => api.put(`/todos/${id}`, data),
  deleteTodo: (id) => api.delete(`/todos/${id}`),
}

async function downloadExcel(resource) {
  try {
    const isDatabase = resource === 'database'
    const blob = await api.get(isDatabase ? '/import-export/database/export' : `/import-export/export/${resource}`, { responseType: 'blob', timeout: 300000 })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const today = new Date()
    const date = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`
    link.href = url
    link.download = isDatabase ? `mouse-manager_${date}_${today.getTime()}.db` : `${resource}_export_${date}.xlsx`
    document.body.appendChild(link)
    try {
      link.click()
    } finally {
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch (error) {
    let data = error.response?.data
    if (data instanceof Blob) {
      try {
        data = JSON.parse(await data.text())
      } catch {
        data = null
      }
    }
    ElMessage.error(data?.detail || '导出失败，请稍后重试')
  }
}

export const importExportApi = {
  exportDatabase: () => downloadExcel('database'),
  restoreDatabase: (formData) => api.post('/import-export/database/restore', formData, { timeout: 300000 }),
  initLocal: () => api.post('/import-export/init-local'),
  uploadExcel: (formData) => api.post('/import-export/upload', formData),
  exportMice: () => downloadExcel('mice'),
  exportCages: () => downloadExcel('cages'),
}

export default api
