<template>
  <div>
    <div class="page-head">
      <div>
        <p>创建和管理 AI Agent 工作团队，复用团队配置并快速发起任务</p>
      </div>
      <el-button type="primary" @click="edit()"
        ><el-icon><Plus /></el-icon> 创建团队</el-button
      >
    </div>
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索团队..."
        clearable
        style="max-width: 300px"
      /><el-tag>{{ filtered.length }} 个团队</el-tag>
    </div>
    <div class="cards">
      <div v-for="t in filtered" :key="t.id" class="team-card">
        <div class="card-top">
          <div class="avatar">
            <el-icon><Connection /></el-icon>
          </div>
          <div style="flex: 1; min-width: 0">
            <div class="card-name">{{ t.name }}</div>
            <div class="card-role">{{ t.is_template ? '模板团队' : '自定义团队' }}</div>
          </div>
          <el-tag size="small" type="warning">{{ t.mode }}</el-tag>
        </div>
        <div class="card-desc">{{ t.description || '暂无描述' }}</div>
        <div class="card-meta">
          <span>团队成员</span><b>{{ t.agent_ids?.length || 0 }} 个 Agent</b>
        </div>
        <div class="member-list">
          <el-tooltip
            v-for="id in (t.agent_ids || []).slice(0, 6)"
            :key="id"
            :content="agentName(id)"
            ><div class="member-avatar">{{ agentName(id).slice(0, 1) }}</div></el-tooltip
          ><span v-if="!t.agent_ids?.length" class="muted">尚未添加成员</span>
        </div>
        <div class="card-metrics">
          <div>
            <div class="metric-num">{{ t.completed_tasks }}</div>
            <div class="metric-label">已完成</div>
          </div>
          <div>
            <div class="metric-num" style="color: var(--orange)">{{ t.running_tasks }}</div>
            <div class="metric-label">进行中</div>
          </div>
        </div>
        <div class="card-actions">
          <el-button @click="edit(t)"
            ><el-icon><Edit /></el-icon> 编辑</el-button
          ><el-button type="primary" plain @click="$emit('use-team', t)"
            ><el-icon><CircleCheck /></el-icon> 使用团队</el-button
          >
        </div>
      </div>
    </div>
    <el-dialog v-model="dialog" :title="form.id ? '编辑团队' : '创建团队'" width="min(650px,94vw)"
      ><el-form :model="form" label-position="top"
        ><el-form-item label="团队名称" required><el-input v-model="form.name" /></el-form-item
        ><el-form-item label="团队描述"
          ><el-input v-model="form.description" type="textarea" :rows="2"
        /></el-form-item>
        <div class="form-grid">
          <el-form-item label="默认协作模式"
            ><el-select v-model="form.mode" style="width: 100%"
              ><el-option
                v-for="m in modes"
                :key="m"
                :label="m"
                :value="m" /></el-select></el-form-item
          ><el-form-item label="模板团队"><el-switch v-model="form.is_template" /></el-form-item>
        </div>
        <el-form-item label="团队成员"
          ><el-select
            v-model="form.agent_ids"
            multiple
            style="width: 100%"
            placeholder="选择需要加入团队的 Agent"
            ><el-option
              v-for="a in agents"
              :key="a.id"
              :label="`${a.name} · ${a.role}`"
              :value="a.id" /></el-select></el-form-item></el-form
      ><template #footer
        ><el-button @click="dialog = false">取消</el-button
        ><el-button type="primary" @click="save">保存</el-button></template
      ></el-dialog
    >
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Connection, Edit, CircleCheck } from '@element-plus/icons-vue'
defineEmits(['use-team'])
const teams = ref([]),
  agents = ref([]),
  search = ref(''),
  dialog = ref(false)
const modes = ['串行', '并行', '自由讨论', '可视化流程编排']
const blank = () => ({ name: '', description: '', mode: '串行', is_template: false, agent_ids: [] })
const form = ref(blank())
const filtered = computed(() =>
  teams.value.filter((t) => t.name.toLowerCase().includes(search.value.toLowerCase()))
)
function agentName(id) {
  return agents.value.find((a) => a.id === id)?.name || `Agent ${id}`
}
function edit(t) {
  form.value = t ? { ...t, agent_ids: [...(t.agent_ids || [])] } : blank()
  dialog.value = true
}
async function load() {
  ;[teams.value, agents.value] = await Promise.all([api.teams(), api.agents()])
}
async function save() {
  if (!form.value.name.trim()) return ElMessage.warning('请填写团队名称')
  try {
    await api.saveTeam(form.value)
    ElMessage.success('团队已保存')
    dialog.value = false
    await load()
  } catch {
    ElMessage.error('保存失败，请检查后端服务')
  }
}
onMounted(() => load())
</script>
<style scoped>
.member-list {
  display: flex;
  gap: 7px;
  align-items: center;
  margin: 13px 0;
}
.member-avatar {
  width: 29px;
  height: 29px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--cyan);
  background: #0b3545;
  border: 1px solid #087e91;
  font-size: 12px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
</style>
