import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Conversations from '../views/Conversations.vue'
import Teams from '../views/Teams.vue'
import Tasks from '../views/Tasks.vue'
import Platform from '../views/Platform.vue'
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: Dashboard },
    { path: '/conversations', component: Conversations },
    { path: '/teams', component: Teams },
    { path: '/tasks', component: Tasks },
    { path: '/platform/:section?', component: Platform }
  ]
})
