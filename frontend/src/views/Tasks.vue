<template>
  <div>
    <div class="page-head">
      <div>
        <p>管理所有任务，查看协作执行状态、进度和结果</p>
      </div>
      <el-button type="primary" @click="$emit('new-task')"
        ><el-icon><Plus /></el-icon> 新建任务</el-button
      >
    </div>
    <div class="grid stat-grid">
      <div v-for="s in stats" :key="s.label" class="stat-card">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
      </div>
    </div>
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索任务..."
        clearable
        style="max-width: 320px"
      /><el-select v-model="status" style="width: 150px"
        ><el-option label="全部状态" value="全部" /><el-option
          label="待执行"
          value="待执行" /><el-option label="进行中" value="进行中" /><el-option
          label="已完成"
          value="已完成" /><el-option label="失败" value="失败" /></el-select
      ><el-button @click="load">刷新</el-button>
    </div>
    <div class="cards">
      <div v-for="t in filtered" :key="t.id" class="team-card">
        <div class="card-top">
          <el-tag :type="tagType(t.status)" effect="dark">{{ t.status }}</el-tag
          ><el-tag style="margin-left: auto" type="info">{{ t.collaboration_mode }}</el-tag>
        </div>
        <h3>{{ t.title }}</h3>
        <p class="card-desc">{{ t.description }}</p>
        <div class="task-owner">
          <el-icon><Connection /></el-icon>{{ t.target_name || '未指定执行对象' }}
        </div>
        <div class="task-row-top">
          <span class="muted">执行进度</span><b>{{ t.progress }}%</b>
        </div>
        <div class="progress-line"><span :style="{ width: t.progress + '%' }"></span></div>
        <div class="card-meta" style="margin-top: 12px">
          <span>创建时间</span><span>{{ formatDate(t.created_at) }}</span>
        </div>
        <div class="card-actions">
          <el-button v-if="t.status === '待执行'" type="primary" plain @click="start(t)"
            >开始</el-button
          ><el-button @click="detail = t">查看详情</el-button>
        </div>
      </div>
    </div>
    <el-empty v-if="!filtered.length" description="没有匹配的任务" /><el-dialog
      :model-value="!!detail"
      title="任务详情"
      width="min(700px,94vw)"
      @close="detail = null"
      ><template v-if="detail"
        ><h3>{{ detail.title }}</h3>
        <p class="muted">{{ detail.description }}</p>
        <el-descriptions :column="2" border
          ><el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item
          ><el-descriptions-item label="协作模式">{{
            detail.collaboration_mode
          }}</el-descriptions-item
          ><el-descriptions-item label="执行对象">{{ detail.target_name }}</el-descriptions-item
          ><el-descriptions-item label="进度"
            >{{ detail.progress }}%</el-descriptions-item
          ></el-descriptions
        >
        <div
          v-if="detail.collaboration_mode === '可视化流程编排'"
          class="workflow-board"
          style="margin-top: 18px"
        >
          <div class="workflow-row">
            <div
              v-for="(n, i) in detail.workflow?.nodes || defaultNodes"
              :key="i"
              class="workflow-node"
            >
              <b>{{ n.name || n }}</b>
              <p class="muted">Agent 执行节点</p>
            </div>
          </div>
        </div>
        <h4>执行结果</h4>
        <p class="result-box">
          {{ detail.result || '任务尚未完成，执行结果将在此展示。' }}
        </p></template
      ></el-dialog
    >
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import { Plus, Connection } from '@element-plus/icons-vue'
defineEmits(['new-task'])
const tasks = ref([]),
  search = ref(''),
  status = ref('全部'),
  detail = ref(null)
const defaultNodes = [{ name: '需求分析' }, { name: '方案设计' }, { name: '执行与审查' }]
const filtered = computed(() =>
  tasks.value.filter(
    (t) =>
      (status.value === '全部' || t.status === status.value) &&
      t.title.toLowerCase().includes(search.value.toLowerCase())
  )
)
const stats = computed(() => [
  { label: '全部任务', value: tasks.value.length, color: 'var(--cyan)' },
  {
    label: '待执行',
    value: tasks.value.filter((t) => t.status === '待执行').length,
    color: 'var(--orange)'
  },
  {
    label: '进行中',
    value: tasks.value.filter((t) => t.status === '进行中').length,
    color: '#2bafff'
  },
  {
    label: '已完成',
    value: tasks.value.filter((t) => t.status === '已完成').length,
    color: 'var(--green)'
  }
])
function tagType(s) {
  return s === '已完成'
    ? 'success'
    : s === '进行中'
      ? 'primary'
      : s === '失败'
        ? 'danger'
        : 'warning'
}
function formatDate(s) {
  return s ? new Date(s + 'Z').toLocaleString() : '—'
}
async function load() {
  try {
    tasks.value = await api.tasks()
  } catch {
    ElMessage.error('无法读取任务，请检查后端是否启动')
  }
}
async function start(t) {
  try {
    await api.startTask(t.id)
    window.dispatchEvent(new Event('tasks-changed'))
    ElMessage.success('任务已进入演示执行状态')
    await load()
  } catch {
    ElMessage.error('启动失败')
  }
}
onMounted(load)
</script>
<style scoped>
h3 {
  font-size: 16px;
  margin: 17px 0 8px;
}
.task-owner {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--cyan);
  font-size: 12px;
  padding: 10px;
  background: #0c2132;
  border-radius: 7px;
  margin: 10px 0 15px;
}
.result-box {
  background: #0c1b2b;
  border: 1px solid #1b354b;
  border-radius: 8px;
  padding: 14px;
  white-space: pre-wrap;
  color: #c5d4e7;
  font-size: 13px;
}
.workflow-board {
  min-height: 150px;
}
.workflow-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
