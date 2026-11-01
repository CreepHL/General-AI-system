<template>
  <div :class="['app-shell', { 'light-mode': light }]">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">✳</div>
        <div><strong>General AI System</strong><small>Multi-Agent Workspace</small></div>
      </div>
      <div class="nav-label">WORKSPACE</div>
      <router-link
        v-for="item in nav"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: $route.path.startsWith(item.path) }"
        ><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span
        ><span v-if="item.path === '/tasks' && runningCount > 0" class="nav-badge">{{ runningCount }}</span></router-link
      >
      <div class="sidebar-bottom">
        <div class="online-dot"></div>
        <span>系统运行正常</span><span class="version">v0.1.0</span>
      </div>
    </aside>
    <main class="main-shell">
      <div class="ambient-sky" aria-hidden="true">
        <span class="meteor meteor-1"></span>
        <span class="meteor meteor-2"></span>
        <span class="meteor meteor-3"></span>
        <span class="meteor meteor-4"></span>
        <span class="meteor meteor-5"></span>
      </div>
      <header class="topbar">
        <div class="top-title">
          <div class="eyebrow">GENERAL AI PLATFORM</div>
          <div class="top-page">{{ pageTitle }}</div>
        </div>
        <div class="top-actions">
          <el-tooltip content="切换语言"
            ><el-dropdown @command="lang = $event"
              ><span class="top-icon"
                ><el-icon><Compass /></el-icon><small>{{ lang }}</small></span
              ><template #dropdown
                ><el-dropdown-menu
                  ><el-dropdown-item command="中文">中文</el-dropdown-item
                  ><el-dropdown-item command="EN">English</el-dropdown-item></el-dropdown-menu
                ></template
              ></el-dropdown
            ></el-tooltip
          >
          <el-tooltip :content="light ? '切换暗色模式' : '切换亮色模式'"
            ><button class="icon-button" @click="light = !light">
              <el-icon><Sunny v-if="light" /><Moon v-else /></el-icon></button
          ></el-tooltip>
          <el-tooltip content="全屏"
            ><button class="icon-button" @click="fullscreen">
              <el-icon><FullScreen /></el-icon></button
          ></el-tooltip>
          <div class="user-chip">
            <div class="user-avatar">V</div>
            <div><b>Visitor</b><small>Administrator</small></div>
            <el-icon><ArrowDown /></el-icon>
          </div>
        </div>
      </header>
      <div class="page-content">
        <router-view v-slot="{ Component }"
          ><component :is="Component" @new-task="openTask" @use-team="useTeam"
        /></router-view>
      </div>
    </main>
    <el-dialog v-model="taskDialog" title="新建任务" width="min(760px, 94vw)" destroy-on-close>
      <el-form :model="form" label-position="top"
        ><div class="form-grid">
          <el-form-item label="任务名称" required
            ><el-input
              v-model="form.title"
              placeholder="例如：设计一个客户服务 Agent" /></el-form-item
          ><el-form-item label="执行对象"
            ><el-select v-model="form.target_type" style="width: 100%"
              ><el-option label="团队" value="team" /><el-option
                label="单个 Agent"
                value="agent" /></el-select
          ></el-form-item>
        </div>
        <el-form-item label="任务描述" required
          ><el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="描述目标、背景、约束和期望交付物..."
        /></el-form-item>
        <div class="form-grid">
          <el-form-item :label="form.target_type === 'team' ? '执行团队' : '执行 Agent'"
            ><el-select
              v-model="form.target_id"
              style="width: 100%"
              placeholder="请选择"
              @change="syncTarget"
              ><el-option
                v-for="x in targets"
                :key="x.id"
                :label="x.name"
                :value="x.id" /></el-select></el-form-item
          ><el-form-item label="协作模式"
            ><el-select v-model="form.collaboration_mode" style="width: 100%"
              ><el-option label="串行协作" value="串行" /><el-option
                label="并行协作"
                value="并行" /><el-option label="自由讨论" value="自由讨论" /><el-option
                label="可视化流程编排"
                value="可视化流程编排" /></el-select
          ></el-form-item>
        </div>
        <div v-if="form.collaboration_mode === '可视化流程编排'" class="workflow-mini">
          <div class="workflow-head">
            <b>团队内 Agent 流程编排</b
            ><el-button size="small" @click="addNode">+ 添加节点</el-button>
          </div>
          <div v-for="(node, index) in form.workflow.nodes" :key="index" class="mini-flow-edit">
            <span class="node-index">{{ index + 1 }}</span
            ><el-input v-model="node.name" placeholder="节点名称" /><el-select
              v-model="node.agent_id"
              clearable
              placeholder="绑定 Agent"
              style="width: 180px"
              ><el-option
                v-for="a in agents"
                :key="a.id"
                :label="a.name"
                :value="a.id" /></el-select
            ><el-button text type="danger" @click="removeNode(index)">删除</el-button
            ><i v-if="index < form.workflow.nodes.length - 1" class="flow-link">↓</i>
          </div>
          <p>节点按从上到下的顺序执行。当前版本保存编排定义，真实执行引擎需要后续接入。</p>
        </div> </el-form
      ><template #footer
        ><el-button @click="taskDialog = false">取消</el-button
        ><el-button type="primary" :loading="saving" @click="submitTask"
          >创建任务</el-button
        ></template
      >
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Grid,
  ChatDotRound,
  User,
  UserFilled,
  Checked,
  Setting,
  Compass,
  Sunny,
  Moon,
  FullScreen,
  ArrowDown,
  Connection,
  Collection,
  DataAnalysis
} from '@element-plus/icons-vue'
import { api } from './api'
import { ElMessage } from 'element-plus'
const route = useRoute(),
  router = useRouter(),
  light = ref(localStorage.getItem('theme') !== 'dark'),
  lang = ref('中文'),
  taskDialog = ref(false),
  saving = ref(false),
  teams = ref([]),
  agents = ref([]),
  runningCount = ref(0)
let runningCountTimer
async function refreshRunningCount() {
  try {
    runningCount.value = await api.runningTaskCount()
  } catch { /* retain the last known count while the API is unavailable */ }
}
onMounted(() => {
  refreshRunningCount()
  runningCountTimer = window.setInterval(refreshRunningCount, 10000)
  window.addEventListener('focus', refreshRunningCount)
  window.addEventListener('tasks-changed', refreshRunningCount)
})
onUnmounted(() => {
  window.clearInterval(runningCountTimer)
  window.removeEventListener('focus', refreshRunningCount)
  window.removeEventListener('tasks-changed', refreshRunningCount)
})
watch(
  light,
  (value) => {
    document.body.classList.toggle('light-mode', value)
    localStorage.setItem('theme', value ? 'light' : 'dark')
  },
  { immediate: true }
)
const nav = [
  { label: '首页', path: '/dashboard', icon: Grid },
  { label: '对话与任务', path: '/conversations', icon: ChatDotRound },
  { label: '团队管理', path: '/teams', icon: Connection },
  { label: '任务大厅', path: '/tasks', icon: Checked },
  { label: '平台配置', path: '/platform/models', icon: Setting }
]
const pageTitle = computed(() =>
  route.path.startsWith('/platform')
    ? '平台配置'
    : route.path.startsWith('/conversations')
      ? '对话与任务'
      : route.path.startsWith('/teams')
        ? '团队管理'
        : route.path.startsWith('/tasks')
          ? '任务大厅'
          : '控制台'
)
const form = ref({
  title: '',
  description: '',
  target_type: 'team',
  target_id: null,
  target_name: '',
  team_id: null,
  collaboration_mode: '串行',
  workflow: { nodes: [{ name: '需求分析' }, { name: '方案设计' }, { name: '执行与审查' }] }
})
const targets = computed(() => (form.value.target_type === 'team' ? teams.value : agents.value))
watch(
  () => form.value.target_type,
  () => {
    form.value.target_id = null
    form.value.target_name = ''
    form.value.team_id = null
  }
)
async function openTask(payload = {}) {
  try {
    teams.value = await api.teams()
    agents.value = await api.agents()
  } catch {}
  form.value = {
    title: payload.title || '',
    description: payload.description || '',
    target_type: payload.type || 'team',
    target_id: payload.id || null,
    target_name: payload.name || '',
    team_id: payload.type === 'team' ? payload.id : null,
    collaboration_mode: payload.mode || '串行',
    workflow: {
      nodes: [
        { name: '需求分析', agent_id: null },
        { name: '方案设计', agent_id: null },
        { name: '执行与审查', agent_id: null }
      ]
    }
  }
  taskDialog.value = true
}
function useTeam(team) {
  openTask({ type: 'team', id: team.id, name: team.name, mode: team.mode })
  router.push('/tasks')
}
function addNode() {
  form.value.workflow.nodes.push({ name: '新节点', agent_id: null })
}
function removeNode(index) {
  if (form.value.workflow.nodes.length > 1) form.value.workflow.nodes.splice(index, 1)
}
function syncTarget(id) {
  const x = targets.value.find((i) => i.id === id)
  form.value.target_name = x?.name || ''
  form.value.team_id = form.value.target_type === 'team' ? id : null
}
async function submitTask() {
  if (!form.value.title.trim() || !form.value.description.trim()) {
    ElMessage.warning('请填写任务名称和描述')
    return
  }
  syncTarget(form.value.target_id)
  saving.value = true
  try {
    await api.createTask(form.value)
    window.dispatchEvent(new Event('tasks-changed'))
    ElMessage.success('任务已创建')
    taskDialog.value = false
    router.push('/tasks')
  } catch (e) {
    ElMessage.error('创建失败，请确认 FastAPI 后端已启动')
  } finally {
    saving.value = false
  }
}
function fullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.()
  else document.exitFullscreen?.()
}
</script>
<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  color: #e8f1ff;
}
.app-shell.light-mode {
  color: #1a2d43;
}
.sidebar {
  width: 226px;
  flex-shrink: 0;
  border-right: 1px solid rgba(0, 218, 255, 0.15);
  background: rgba(7, 14, 24, 0.96);
  display: flex;
  flex-direction: column;
  padding: 20px 13px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 9px 28px;
}
.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  color: #07121d;
  background: linear-gradient(135deg, #12e8ff, #3d8bff);
  border-radius: 11px;
  font-size: 24px;
  font-weight: bold;
}
.brand strong {
  display: block;
  font-size: 14px;
  letter-spacing: 0.1px;
}
.brand small {
  display: block;
  color: #758ba6;
  font-size: 10px;
  margin-top: 4px;
}
.nav-label {
  color: #566b83;
  font-size: 10px;
  letter-spacing: 1.6px;
  padding: 0 13px 10px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #91a5bf;
  padding: 13px 14px;
  border-radius: 9px;
  margin-bottom: 5px;
  font-size: 13px;
  text-decoration: none;
  transition: 0.2s;
}
.nav-item .el-icon {
  font-size: 17px;
}
.nav-item.active,
.nav-item:hover {
  background: linear-gradient(90deg, #063746, #0c2435);
  color: #13eaff;
  box-shadow: inset 3px 0 #12e8ff;
}
.nav-badge {
  margin-left: auto;
  background: #e83b70;
  color: white;
  border-radius: 20px;
  font-size: 10px;
  padding: 2px 7px;
}
.sidebar-bottom {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 15px 9px;
  color: #7d93ac;
  font-size: 11px;
  border-top: 1px solid #182b3f;
}
.online-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00e6a0;
  box-shadow: 0 0 8px #00e6a0;
}
.version {
  margin-left: auto;
}
.main-shell {
  flex: 1;
  min-width: 0;
}
.topbar {
  height: 78px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 30px;
  border-bottom: 1px solid rgba(0, 218, 255, 0.12);
  background: rgba(8, 15, 26, 0.68);
  backdrop-filter: blur(14px);
}
.top-page {
  font-size: 18px;
  font-weight: 650;
  margin-top: 4px;
}
.top-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.top-icon,
.icon-button {
  height: 36px;
  min-width: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: #9bb0c8;
  border: 1px solid #20394f;
  background: #0e1a2b;
  border-radius: 9px;
  cursor: pointer;
  padding: 0 10px;
}
.top-icon small {
  font-size: 11px;
}
.icon-button:hover,
.top-icon:hover {
  color: #12e8ff;
  border-color: #12e8ff;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding-left: 12px;
  border-left: 1px solid #203246;
}
.user-avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #00d9ef, #8d3cff);
  font-weight: 700;
  color: #06111d;
}
.user-chip b,
.user-chip small {
  display: block;
}
.user-chip b {
  font-size: 12px;
}
.user-chip small {
  font-size: 10px;
  color: #7e92ab;
  margin-top: 3px;
}
.user-chip > .el-icon {
  color: #8298b0;
}
.page-content {
  padding: 26px 28px 38px;
  max-width: 1800px;
  margin: 0 auto;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.workflow-mini {
  background: #0d1b2d;
  border: 1px dashed #23556b;
  border-radius: 10px;
  padding: 14px;
}
.workflow-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mini-flow-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0;
  flex-wrap: wrap;
}
.node-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #10344a;
  color: #12e8ff;
  font-size: 11px;
}
.mini-flow-edit .el-input {
  width: 180px;
}
.flow-link {
  color: #12e8ff;
  font-style: normal;
}
.workflow-mini p {
  font-size: 11px;
  color: #7f91ab;
  margin: 8px 0 0;
}
@media (max-width: 850px) {
  .sidebar {
    width: 70px;
    padding: 16px 7px;
  }
  .brand {
    padding: 4px 7px 24px;
  }
  .brand > div:last-child,
  .nav-label,
  .nav-item span,
  .sidebar-bottom span:not(.online-dot) {
    display: none;
  }
  .nav-item {
    justify-content: center;
    padding: 13px 0;
  }
  .topbar {
    padding: 0 14px;
  }
  .page-content {
    padding: 18px 14px;
  }
  .user-chip > div:not(.user-avatar),
  .user-chip > .el-icon {
    display: none;
  }
}
@media (max-width: 520px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .top-actions {
    gap: 5px;
  }
  .topbar {
    height: 68px;
  }
}
</style>
