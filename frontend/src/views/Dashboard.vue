<template>
  <div>
    <div class="page-head">
      <div>
        <p>实时监控 AI Agent 团队协作与任务运行状态</p>
      </div>
    </div>
    <div class="grid stat-grid">
      <div v-for="s in stats" :key="s.label" class="stat-card" :style="{ '--glow': s.glow }">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="stat-note">{{ s.note }}</div>
      </div>
    </div>
    <div class="split">
      <section class="panel">
        <div class="panel-title">
          <el-icon><Lightning /></el-icon>快捷入口
        </div>
        <div class="quick-grid">
          <div v-for="q in quick" :key="q.title" class="quick-item" @click="q.action()">
            <div class="quick-icon">
              <el-icon><component :is="q.icon" /></el-icon>
            </div>
            <div>
              <b>{{ q.title }}</b>
              <div class="muted" style="font-size: 11px; margin-top: 4px">{{ q.desc }}</div>
            </div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-title">
          <el-icon><Timer /></el-icon>进行中的任务
          <el-tag style="margin-left: auto" size="small" type="info">{{ running.length }}</el-tag>
        </div>
        <div v-if="running.length">
          <div v-for="t in running" :key="t.id" class="task-row">
            <div class="task-row-top">
              <span>{{ t.title }}</span
              ><b style="color: var(--cyan)">{{ t.progress }}%</b>
            </div>
            <div class="progress-line"><span :style="{ width: t.progress + '%' }"></span></div>
            <small class="muted">{{ t.target_name }} · {{ t.collaboration_mode }}</small>
          </div>
        </div>
        <div v-else class="empty">当前没有运行中的任务</div>
      </section>
    </div>
    <div class="split" style="margin-top: 16px">
      <section class="panel">
        <div class="panel-title">
          <el-icon><UserFilled /></el-icon>Agent 状态监控
        </div>
        <div class="agent-mini-grid">
          <div v-for="a in agents.slice(0, 6)" :key="a.id" class="agent-mini">
            <div class="avatar">
              <el-icon><User /></el-icon>
            </div>
            <div class="agent-mini-info">
              <b>{{ a.name }}</b
              ><small>{{ a.role }} · {{ a.completed_tasks }} 项完成</small>
            </div>
            <el-tag size="small" :type="a.enabled ? 'success' : 'info'">{{
              a.enabled ? '在线' : '离线'
            }}</el-tag>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-title">
          <el-icon><Clock /></el-icon>最近活动
        </div>
        <div v-for="a in activities" :key="a.id" class="activity">
          <div class="activity-dot"></div>
          <div>
            <b>{{ a.title }}</b>
            <div class="muted" style="margin-top: 4px">{{ a.detail }}</div>
          </div>
        </div>
      </section>
    </div>
    <section class="panel" style="margin-top: 16px">
      <div class="panel-title">
        <el-icon><ChatDotRound /></el-icon>与 AI 团队开始协作
      </div>
      <p class="muted" style="font-size: 13px; margin-top: -5px">
        描述你的目标，选择一个 Agent 或团队作为执行对象。
      </p>
      <div class="chat-bar">
        <el-select v-model="targetType" style="width: 140px"
          ><el-option label="选择团队" value="team" /><el-option
            label="选择 Agent"
            value="agent" /></el-select
        ><el-select v-model="targetId" placeholder="选择执行对象" style="width: 240px"
          ><el-option v-for="x in choices" :key="x.id" :label="x.name" :value="x.id" /></el-select
        ><el-input
          v-model="prompt"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 3 }"
          placeholder="例如：分析这个项目的架构，并输出实施计划..."
          @keydown.ctrl.enter="$emit('new-task', payload)"
        /><el-button type="primary" :icon="Promotion" @click="$emit('new-task', payload)"
          >创建任务</el-button
        >
      </div>
      <div class="chat-caption">任务创建后可在任务大厅查看进度 · Ctrl + Enter 快捷操作</div>
    </section>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import {
  Plus,
  Lightning,
  Timer,
  UserFilled,
  User,
  Clock,
  ChatDotRound,
  Promotion,
  Connection,
  Checked,
  Collection,
  Setting,
  DocumentAdd
} from '@element-plus/icons-vue'
const emit = defineEmits(['new-task'])
const router = useRouter()
const dash = ref({})
const agents = ref([])
const teams = ref([])
const tasks = ref([])
const prompt = ref('')
const targetType = ref('team')
const targetId = ref(null)
const running = computed(() => tasks.value.filter((t) => t.status === '进行中'))
const activities = computed(() => dash.value.activities || [])
const choices = computed(() => (targetType.value === 'team' ? teams.value : agents.value))
const payload = computed(() => ({
  type: targetType.value,
  id: targetId.value,
  name: choices.value.find((x) => x.id === targetId.value)?.name,
  description: prompt.value,
  title: prompt.value.slice(0, 40) || '新建 AI 任务'
}))
const stats = computed(() => [
  {
    label: 'Agent 总数',
    value: dash.value.agent_count ?? '—',
    note: '已配置的智能体',
    color: 'var(--cyan)',
    glow: 'rgba(0,229,255,.13)'
  },
  {
    label: '团队数量',
    value: dash.value.team_count ?? '—',
    note: '可复用协作团队',
    color: 'var(--purple)',
    glow: 'rgba(210,60,255,.14)'
  },
  {
    label: '任务总数',
    value: dash.value.task_count ?? '—',
    note: '任务累计记录',
    color: 'var(--orange)',
    glow: 'rgba(255,178,28,.13)'
  },
  {
    label: '今日完成',
    value: dash.value.completed_today ?? '—',
    note: '任务完成记录',
    color: 'var(--green)',
    glow: 'rgba(0,230,160,.13)'
  }
])
const quick = [
  {
    title: '创建 Agent',
    desc: '定义角色、模型与工具',
    icon: User,
    action: () => router.push('/platform/agents')
  },
  {
    title: '创建团队',
    desc: '组合多个 Agent',
    icon: Connection,
    action: () => router.push('/teams')
  },
  { title: '下发任务', desc: '选择执行对象与模式', icon: Checked, action: () => emit('new-task') },
  {
    title: '知识库管理',
    desc: '文档与检索资源',
    icon: Collection,
    action: () => router.push('/platform/knowledge')
  },
  {
    title: '平台配置',
    desc: '模型、Prompt、Skill',
    icon: Setting,
    action: () => router.push('/platform/models')
  },
  {
    title: '创建工作流',
    desc: '可视化编排 Agent 节点',
    icon: DocumentAdd,
    action: () => emit('new-task', { mode: '可视化流程编排' })
  }
]
onMounted(async () => {
  try {
    ;[dash.value, agents.value, teams.value, tasks.value] = await Promise.all([
      api.dashboard(),
      api.agents(),
      api.teams(),
      api.tasks()
    ])
  } catch {}
})
</script>
<style scoped>
.agent-mini-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.agent-mini {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid #1b344a;
  border-radius: 9px;
  background: #0e1d2e;
}
.agent-mini .avatar {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}
.agent-mini-info {
  min-width: 0;
  flex: 1;
}
.agent-mini-info b,
.agent-mini-info small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agent-mini-info b {
  font-size: 12px;
}
.agent-mini-info small {
  font-size: 10px;
  color: var(--muted);
  margin-top: 4px;
}
@media (max-width: 700px) {
  .agent-mini-grid {
    grid-template-columns: 1fr;
  }
  .chat-bar {
    flex-wrap: wrap;
  }
  .chat-bar .el-textarea {
    flex-basis: 100%;
  }
}
</style>
