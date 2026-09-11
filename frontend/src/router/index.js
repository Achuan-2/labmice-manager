import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '总览看板' }
  },
  {
    path: '/mice',
    name: 'MiceList',
    component: () => import('@/views/MiceList.vue'),
    meta: { title: '小鼠列表' }
  },
  {
    path: '/cages',
    name: 'CageRack',
    component: () => import('@/views/CageRack.vue'),
    meta: { title: '笼位管理' }
  },
  {
    path: '/todos',
    name: 'TodoReminders',
    component: () => import('@/views/TodoReminders.vue'),
    meta: { title: '待办提醒', adminOnly: true }
  },
  {
    path: '/transfer-requests',
    name: 'TransferRequests',
    component: () => import('@/views/TransferRequests.vue'),
    meta: { title: '转鼠需求及反馈表' }
  },
  {
    path: '/genotypes',
    name: 'Genotypes',
    component: () => import('@/views/Genotypes.vue'),
    meta: { title: '基因鉴定结果' }
  },
  {
    path: '/members',
    name: 'Members',
    component: () => import('@/views/Members.vue'),
    meta: { title: '课题组成员' }
  },
  {
    path: '/claimers',
    redirect: '/members'
  },
  {
    path: '/transfers',
    name: 'Transfers',
    component: () => import('@/views/Transfers.vue'),
    meta: { title: '领用与流转日志' }
  },
  {
    path: '/import-export',
    name: 'ImportExport',
    component: () => import('@/views/ImportExport.vue'),
    meta: { title: '数据导入导出' }
  },
  {
    path: '/admins',
    name: 'AdminUsers',
    component: () => import('@/views/AdminUsers.vue'),
    meta: { title: '管理员设置', adminOnly: true }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta?.adminOnly) {
    const rawUser = localStorage.getItem('mouse_lab_user')
    const token = localStorage.getItem('mouse_lab_token')
    let user = null
    try {
      user = JSON.parse(rawUser || 'null')
    } catch {
      user = null
    }
    const isAdmin = !!token && user?.role === 'admin'
    if (!isAdmin) {
      next('/')
      return
    }
  }
  next()
})

export default router
