<template>
  <div>
    <div class="page-head">
      <div>
        <p>统一管理模型、智能体、Prompt、Skill、Tools、知识库和成本使用情况</p>
      </div>
      <el-button v-if="section !== 'costs'" type="primary" @click="edit()"
        ><el-icon><Plus /></el-icon> 新增{{ currentName }}</el-button
      >
    </div>
    <div class="config-nav">
      <el-button
        v-for="x in sections"
        :key="x.key"
        :type="section === x.key ? 'primary' : 'default'"
        plain
        @click="go(x.key)"
        ><el-icon><component :is="x.icon" /></el-icon>{{ x.label }}</el-button
      >
    </div>
    <template v-if="section === 'costs'"
      ><div class="grid stat-grid">
        <div v-for="s in costStats" :key="s.label" class="stat-card">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
          <div class="stat-note">{{ s.note || '实际调用记录' }}</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">
          <el-icon><DataAnalysis /></el-icon>按日成本与 Token 使用
          <el-select v-model="chartCurrency" size="small" style="width: 112px; margin-left: auto" @change="draw">
            <el-option label="CNY" value="CNY" /><el-option label="USD" value="USD" />
          </el-select>
        </div>
        <div ref="chart" style="height: 310px"></div>
      </div>
      <div class="panel" style="margin-top: 16px">
        <p class="muted">
          仅统计本系统接入记录后的成功模型调用（含连接测试）。Token 取供应商返回的 usage；未返回用量的调用不计入 Token。
          成本按模型配置的每百万输入/输出 Token 单价估算，未配置价格的调用不计入成本；不同币种分别展示，不做隐含换算。
        </p>
      </div></template
    >
    <template v-else
      ><div class="toolbar">
        <el-input
          v-model="search"
          clearable
          placeholder="搜索名称、标识或描述..."
          style="max-width: 360px"
        /><el-tag>{{ filtered.length }} 项配置</el-tag>
      </div>
      <div class="cards">
        <div v-for="item in filtered" :key="item.id" class="config-card">
          <div class="card-top">
            <div class="avatar">
              <el-icon><component :is="sectionIcon" /></el-icon>
            </div>
            <div style="flex: 1; min-width: 0">
              <div class="card-name">{{ item.name }}</div>
              <div class="card-role">{{ item.code || item.provider || section.toUpperCase() }}</div>
            </div>
            <div class="card-state">
              <el-tag size="small" :type="(section === 'agents' ? item.enabled : item.status === '已启用') ? 'success' : 'info'">{{ item.status }}</el-tag>
              <el-switch v-if="section === 'models'" :model-value="item.status === '已启用'"
                :loading="togglingId === item.id" :disabled="togglingId !== null"
                :aria-label="item.name + '启用或停用'" @change="toggle(item)" />
            </div>
          </div>
          <div class="desc">{{ item.description || '暂无说明' }}</div>
          <div class="card-meta">
            <span>{{
              section === 'models'
                ? '模型标识'
                : section === 'knowledge'
                  ? '文档数量'
                  : '版本 / 标识'
            }}</span
            ><b>{{
              section === 'models'
                ? item.model_name
                : section === 'knowledge'
                  ? (item.document_count || 0) + ' 份'
                  : '已登记'
            }}</b>
          </div>
          <div v-if="section === 'models'" class="tag-row">
            <el-tag size="small" type="info">{{ item.provider || '自定义供应商' }}</el-tag
            ><el-tag v-if="item.is_default" size="small" type="warning">默认模型</el-tag
            ><el-tag size="small" type="info">{{
              item.api_key ? 'Key 已配置' : 'Key 未配置'
            }}</el-tag>
          </div>
          <div class="card-actions">
            <el-button @click="edit(item)"
              ><el-icon><Edit /></el-icon> 编辑</el-button
            ><el-button v-if="section === 'models'" type="primary" plain @click="testModel(item)"
              >连接测试</el-button
            ><el-button
              v-else-if="section === 'knowledge'"
              type="primary"
              plain
              @click="openKnowledge(item)"
              >查看</el-button
            ><el-button v-else type="primary" plain @click="toggle(item)">{{
              item.status === '已启用' ? '停用' : '启用'
            }}</el-button
            ><el-button type="danger" plain @click="remove(item)">删除</el-button>
          </div>
        </div>
      </div>
      <el-empty v-if="!filtered.length" description="没有匹配的配置"
    /></template>
    <el-dialog v-model="knowledgeDialog" :title="knowledgeBase?.name || '知识库'" width="min(760px,94vw)">
      <div class="knowledge-actions">
        <input ref="knowledgeFile" type="file" accept=".txt,.md,.csv,.json,.pdf" multiple style="display:none" @change="uploadKnowledgeFiles" />
        <el-button type="primary" :loading="knowledgeUploading" @click="knowledgeFile?.click()">上传文档</el-button>
        <span class="muted">支持 TXT、MD、CSV、JSON、文本型 PDF；每份不超过 12 MB</span>
      </div>
      <el-input v-model="knowledgeQuery" placeholder="输入关键词检索知识库" clearable @keydown.enter="searchKnowledgeBase">
        <template #append><el-button @click="searchKnowledgeBase">检索</el-button></template>
      </el-input>
      <div v-if="knowledgeQuery && knowledgeResults.length" class="knowledge-results">
        <div v-for="hit in knowledgeResults" :key="hit.chunk_id" class="knowledge-hit">
          <strong>{{ hit.filename }}</strong><p>{{ hit.content }}</p>
        </div>
      </div>
      <p v-else-if="knowledgeSearched" class="muted">没有找到匹配片段</p>
      <h3>文档（{{ knowledgeDocuments.length }}）</h3>
      <div v-for="doc in knowledgeDocuments" :key="doc.id" class="knowledge-document">
        <span>{{ doc.filename }} <small class="muted">{{ doc.chunk_count }} 个片段 · {{ Math.ceil(doc.size / 1024) }} KB</small></span>
        <el-button type="danger" text @click="removeKnowledgeDocument(doc)">删除</el-button>
      </div>
      <el-empty v-if="!knowledgeDocuments.length" description="暂无文档，上传后即可检索" />
    </el-dialog>
    <el-dialog
      v-model="dialog"
      :title="form.id ? '编辑' + currentName : '新增' + currentName"
      width="min(780px,94vw)"
      destroy-on-close
      ><el-form :model="form" label-position="top"
        ><div class="form-grid">
          <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item
          ><el-form-item label="标识 / Code"><el-input v-model="form.code" /></el-form-item>
        </div>
        <template v-if="section === 'agents'"
          ><div class="form-grid">
            <el-form-item label="角色"
              ><el-input
                v-model="form.role"
                placeholder="如：研究员、架构师、测试工程师" /></el-form-item
            ><el-form-item label="绑定模型"
              ><el-select
                v-model="form.model_config_id"
                clearable
                filterable
                placeholder="选择已配置模型"
                style="width: 100%"
                @change="syncModelName"
              >
                <el-option
                  v-for="model in modelOptions"
                  :key="model.id"
                  :label="model.name + ' · ' + model.model_name"
                  :value="model.id"
                /> </el-select
            ></el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="Temperature"
              ><el-input-number
                v-model="form.temperature"
                :min="0"
                :max="2"
                :step="0.1" /></el-form-item
            ><el-form-item label="记忆类型"
              ><el-select v-model="form.memory_type" style="width: 100%"
                ><el-option label="短期记忆" value="短期记忆" /><el-option
                  label="长期记忆"
                  value="长期记忆" /></el-select
            ></el-form-item>
          </div>
          <el-form-item label="系统 Prompt"
            ><el-input
              v-model="form.prompt"
              type="textarea"
              :rows="6"
              placeholder="定义 Agent 的身份、职责、工作方式和输出格式" /></el-form-item
          ><el-form-item label="绑定 Prompt（可选）">
            <el-select
              v-model="form.prompt_config_id"
              clearable
              filterable
              placeholder="选择平台 Prompt"
              style="width: 100%"
            >
              <el-option
                v-for="prompt in promptOptions"
                :key="prompt.id"
                :label="prompt.name"
                :value="prompt.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="绑定 Skill（可多选）">
            <el-select
              v-model="form.skill_config_ids"
              multiple
              collapse-tags
              filterable
              placeholder="选择平台 Skill"
              style="width: 100%"
            >
              <el-option
                v-for="skill in skillOptions"
                :key="skill.id"
                :label="skill.name"
                :value="skill.id"
              />
            </el-select> </el-form-item
          ><el-form-item label="绑定工具（逗号分隔）"
            ><el-input
              :model-value="(form.tools || []).join(', ')"
              @update:model-value="
                (v) =>
                  (form.tools = v
                    .split(',')
                    .map((x) => x.trim())
                    .filter(Boolean))
              "
              placeholder="网页检索, 文档生成, 代码审查" /></el-form-item
          ><el-form-item label="启用状态"
            ><el-switch v-model="form.enabled" /></el-form-item></template
        ><template v-if="section === 'models'"
          ><div class="form-grid">
            <el-form-item label="供应商"
              ><el-select v-model="form.provider" style="width: 100%"
                ><el-option label="OpenAI Compatible" value="openai-compatible" /><el-option
                  label="DeepSeek"
                  value="deepseek" /><el-option label="OpenAI" value="openai" /><el-option
                  label="Qwen"
                  value="qwen" /><el-option
                  label="自定义"
                  value="custom" /></el-select></el-form-item
            ><el-form-item label="模型名称"
              ><el-input v-model="form.model_name" placeholder="如 deepseek-chat"
            /></el-form-item>
          </div>
          <el-form-item label="Base URL"
            ><el-input
              v-model="form.base_url"
              placeholder="https://api.example.com/v1" /></el-form-item
          ><el-form-item label="API Key"
            ><el-input
              v-model="form.api_key"
              type="password"
              show-password
              placeholder="留空表示不修改已配置密钥"
          /></el-form-item>
          <div class="form-grid">
            <el-form-item label="最大输出 Token">
              <el-input-number
                v-model="form.extra.max_tokens"
                :min="128"
                :max="128000"
                :step="128"
              />
            </el-form-item>
            <el-form-item label="请求超时（秒）">
              <el-input-number v-model="form.extra.timeout_seconds" :min="5" :max="180" :step="5" />
            </el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="输入单价（每百万 Token）">
              <el-input-number v-model="form.extra.input_price_per_million" :min="0" :precision="4" :step="0.1" placeholder="未配置" />
            </el-form-item>
            <el-form-item label="输出单价（每百万 Token）">
              <el-input-number v-model="form.extra.output_price_per_million" :min="0" :precision="4" :step="0.1" placeholder="未配置" />
            </el-form-item>
          </div>
          <el-form-item label="单价币种">
            <el-select v-model="form.extra.price_currency" clearable placeholder="未配置则不估算成本" style="width: 100%">
              <el-option label="人民币 CNY" value="CNY" /><el-option label="美元 USD" value="USD" />
            </el-select>
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="默认模型"><el-switch v-model="form.is_default" /></el-form-item
            ><el-form-item label="状态"
              ><el-select v-model="form.status" style="width: 100%"
                ><el-option label="已启用" value="已启用" /><el-option
                  label="未配置"
                  value="未配置" /><el-option label="已停用" value="已停用" /></el-select
            ></el-form-item></div></template
        ><el-form-item label="说明"
          ><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item
        ><el-form-item
          v-if="['prompts', 'skills'].includes(section)"
          :label="section === 'prompts' ? 'Prompt 正文' : 'SKILL.md 内容'"
          ><el-input
            v-model="form.content"
            type="textarea"
            :rows="9"
            placeholder="编写完整内容、适用场景、输入输出与约束..." /></el-form-item></el-form
      ><template #footer
        ><el-button @click="dialog = false">取消</el-button
        ><el-button type="primary" @click="save">保存配置</el-button></template
      ></el-dialog
    >
  </div>
</template>
<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  Plus,
  Edit,
  Connection,
  User,
  ChatDotRound,
  Document,
  Tools,
  Collection,
  DataAnalysis,
  Setting
} from '@element-plus/icons-vue'
const route = useRoute(),
  router = useRouter()
const sections = [
  { key: 'models', label: '大模型配置', icon: Connection },
  { key: 'agents', label: '智能体配置', icon: User },
  { key: 'prompts', label: 'Prompt 配置', icon: ChatDotRound },
  { key: 'skills', label: 'Skill 配置', icon: Document },
  { key: 'tools', label: 'Tools 工具', icon: Tools },
  { key: 'knowledge', label: '知识库', icon: Collection },
  { key: 'costs', label: '成本看板', icon: DataAnalysis }
]
const section = computed(() =>
  sections.some((x) => x.key === route.params.section) ? route.params.section : 'models'
)
const currentName = computed(
  () =>
    sections
      .find((x) => x.key === section.value)
      ?.label.replace('配置', '')
      .replace(' 工具', '工具') || '配置'
)
const sectionIcon = computed(() => sections.find((x) => x.key === section.value)?.icon || Setting)
const rows = ref([]),
  search = ref(''),
  dialog = ref(false),
  chart = ref(null),
  chartCurrency = ref('CNY'),
  cost = ref({}),
  form = ref(blank())
const knowledgeDialog = ref(false)
const knowledgeBase = ref(null)
const knowledgeDocuments = ref([])
const knowledgeResults = ref([])
const knowledgeQuery = ref('')
const knowledgeSearched = ref(false)
const knowledgeUploading = ref(false)
const knowledgeFile = ref(null)
const togglingId = ref(null)
const modelOptions = ref([]),
  promptOptions = ref([]),
  skillOptions = ref([])
const filtered = computed(() =>
  rows.value.filter((x) =>
    (x.name + ' ' + x.code + ' ' + x.description).toLowerCase().includes(search.value.toLowerCase())
  )
)
const costStats = computed(() => [
  { label: '成功调用次数', value: cost.value.summary?.calls ?? 0, color: 'var(--cyan)' },
  {
    label: '总 Token',
    value: (cost.value.summary?.tokens ?? 0).toLocaleString(),
    color: 'var(--purple)'
  },
  {
    label: '估计成本',
    value: Object.entries(cost.value.summary?.estimated_cost_by_currency || {}).length
      ? Object.entries(cost.value.summary.estimated_cost_by_currency).map(([currency, amount]) =>
          (currency === 'CNY' ? '¥' : '$') + amount.toFixed(4)).join(' / ')
      : '未核算',
    color: 'var(--orange)',
    note: (cost.value.summary?.unpriced_calls ?? 0) + ' 次调用未计价'
  },
  {
    label: '输入 / 输出',
    value: `${cost.value.summary?.input_tokens ?? 0} / ${cost.value.summary?.output_tokens ?? 0}`,
    color: 'var(--green)',
    note: (cost.value.summary?.unreported_usage_calls ?? 0) + ' 次调用未返回用量'
  }
])
function blank() {
  return {
    name: '',
    code: '',
    provider: 'deepseek',
    model_name: '',
    base_url: '',
    api_key: '',
    description: '',
    content: '',
    status: '已启用',
    is_default: false,
    extra: { max_tokens: 3000, timeout_seconds: 60 },
    role: '通用助手',
    temperature: 0.3,
    memory_type: '短期记忆',
    prompt: '',
    tools: [],
    enabled: true,
    model_config_id: null,
    prompt_config_id: null,
    skill_config_ids: []
  }
}
function go(key) {
  router.push('/platform/' + key)
}
async function openKnowledge(item) {
  knowledgeBase.value = item
  knowledgeResults.value = []
  knowledgeQuery.value = ''
  knowledgeSearched.value = false
  knowledgeDialog.value = true
  try {
    knowledgeDocuments.value = await api.knowledgeDocuments(item.id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '读取知识库文档失败')
  }
}
async function uploadKnowledgeFiles(event) {
  const files = [...(event.target.files || [])]
  event.target.value = ''
  if (!files.length || !knowledgeBase.value) return
  knowledgeUploading.value = true
  try {
    for (const file of files) await api.uploadKnowledgeDocument(knowledgeBase.value.id, file)
    knowledgeDocuments.value = await api.knowledgeDocuments(knowledgeBase.value.id)
    await load()
    ElMessage.success('文档已导入并切分')
  } catch (error) {
    knowledgeDocuments.value = await api.knowledgeDocuments(knowledgeBase.value.id)
    await load()
    ElMessage.error(error.response?.data?.detail || '文档导入失败')
  } finally {
    knowledgeUploading.value = false
  }
}
async function removeKnowledgeDocument(doc) {
  try {
    await api.deleteKnowledgeDocument(knowledgeBase.value.id, doc.id)
    knowledgeDocuments.value = await api.knowledgeDocuments(knowledgeBase.value.id)
    knowledgeResults.value = []
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除文档失败')
  }
}
async function searchKnowledgeBase() {
  if (!knowledgeQuery.value.trim() || !knowledgeBase.value) return
  try {
    const result = await api.searchKnowledge(knowledgeQuery.value.trim(), knowledgeBase.value.id)
    knowledgeResults.value = result.items
    knowledgeSearched.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检索失败')
  }
}
async function load() {
  search.value = ''
  if (section.value === 'costs') {
    try {
      cost.value = await api.costs()
      await nextTick()
      draw()
    } catch {
      cost.value = {}
      ElMessage.error('无法读取真实调用记录，请检查后端服务')
    }
    return
  }
  try {
    if (section.value === 'agents') {
      ;[modelOptions.value, promptOptions.value, skillOptions.value] = await Promise.all([
        api.config('models'),
        api.config('prompts'),
        api.config('skills')
      ])
    }
    rows.value = section.value === 'agents' ? await api.agents() : await api.config(section.value)
  } catch {
    rows.value = []
    ElMessage.error('加载失败，请检查后端服务')
  }
}
function edit(x) {
  form.value = x
    ? {
        ...x,
        api_key: '',
        extra: { max_tokens: 3000, timeout_seconds: 60, ...(x.extra || {}) },
        tools: x.tools || [],
        skill_config_ids: x.skill_config_ids || []
      }
    : blank()
  form.value.category = section.value
  dialog.value = true
}
function syncModelName(id) {
  form.value.model_name = modelOptions.value.find((model) => model.id === id)?.model_name || ''
}
async function save() {
  if (!form.value.name.trim()) return ElMessage.warning('请填写名称')
  try {
    if (section.value === 'agents')
      await api.saveAgent({
        ...form.value,
        temperature: Number(form.value.temperature || 0.3),
        tools: form.value.tools || []
      })
    else await api.saveConfig({ ...form.value, category: section.value })
    ElMessage.success('配置已保存')
    dialog.value = false
    await load()
  } catch {
    ElMessage.error('保存失败，请检查后端服务')
  }
}
async function toggle(x) {
  if (togglingId.value !== null) return
  togglingId.value = x.id
  try {
    const updated = section.value === 'agents'
      ? await api.saveAgent({ ...x, enabled: !x.enabled, status: x.enabled ? '离线' : '在线' })
      : await api.setConfigStatus(x.id, x.status === '已启用' ? '已停用' : '已启用')
    Object.assign(x, updated)
    ElMessage.success(updated.status)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
  } finally {
    togglingId.value = null
  }
}
async function remove(x) {
  try {
    await api[section.value === 'agents' ? 'deleteAgent' : 'deleteConfig'](x.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    ElMessage.error('删除失败，请检查后端服务')
  }
}
function testModel(x) {
  api
    .testModel(x.id)
    .then((result) => ElMessage.success(x.name + ' 连接成功：' + result.response))
    .catch((error) => ElMessage.error(error.response?.data?.detail || '模型连接失败'))
}
function draw() {
  if (!chart.value) return
  let c = echarts.getInstanceByDom(chart.value) || echarts.init(chart.value)
  const d = cost.value.by_day || []
  c.setOption({
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#93a8c2' } },
    grid: { left: 45, right: 24, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: d.map((x) => x.date),
      axisLabel: { color: '#8fa4be' },
      axisLine: { lineStyle: { color: '#2a4056' } }
    },
    yAxis: [
      {
        type: 'value',
        name: 'Token',
        axisLabel: { color: '#8fa4be' },
        splitLine: { lineStyle: { color: '#1b2d40' } }
      },
      { type: 'value', name: '成本 ' + chartCurrency.value, axisLabel: { color: '#8fa4be' } }
    ],
    series: [
      {
        name: 'Token',
        type: 'bar',
        data: d.map((x) => x.tokens),
        itemStyle: { color: '#12cde6', borderRadius: [4, 4, 0, 0] }
      },
      {
        name: '成本 ' + chartCurrency.value,
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: d.map((x) => x.cost_by_currency?.[chartCurrency.value] ?? null),
        itemStyle: { color: '#d23cff' }
      }
    ]
  })
}
watch(section, load)
onMounted(load)
</script>
<style scoped>
.desc {
  font-size: 12px;
  line-height: 1.7;
  color: var(--muted);
  margin: 12px 0;
  flex: 1;
}
.config-card {
  min-height: 185px;
}
.card-state { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.knowledge-actions, .knowledge-document { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.knowledge-actions { justify-content: flex-start; margin-bottom: 16px; }
.knowledge-document, .knowledge-hit { padding: 10px 0; border-bottom: 1px solid var(--line); }
.knowledge-document small { margin-left: 8px; }
.knowledge-results { max-height: 240px; overflow: auto; margin: 14px 0; }
.knowledge-hit p { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--muted); }
</style>
