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
          <div v-if="section === 'agents'" class="agent-bindings">
            <div><span>模型</span><b>{{ modelBinding(item) }}</b></div>
            <div><span>Prompt</span><b>{{ promptBinding(item) }}</b></div>
            <div><span>Skill</span><b>{{ bindingSummary(item.skill_config_ids, skillOptions) }}</b></div>
            <div><span>Tools</span><b>{{ bindingSummary(item.tool_config_ids, toolOptions) }}</b></div>
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
              (section === 'agents' ? item.enabled : item.status === '已启用') ? '停用' : '启用'
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
      ><el-form :model="form" label-position="top" class="config-form"
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
          <div class="agent-binding-title">
            <div><strong>角色能力配置</strong><small>选择当前智能体使用的 Prompt、Skill 和 Tools。</small></div>
            <el-button size="small" @click="applyRoleRecommendation">按角色补充推荐</el-button>
          </div>
          <el-form-item label="绑定 Prompt（可选）">
            <el-select v-model="form.prompt_config_id" clearable filterable
              placeholder="选择角色 Prompt" style="width: 100%">
              <el-option v-if="form.prompt_config_id && !selectedPrompt"
                :label="'已删除的 Prompt #' + form.prompt_config_id" :value="form.prompt_config_id" />
              <el-option v-for="prompt in promptOptions" :key="prompt.id"
                :label="prompt.name + (prompt.code ? ' · ' + prompt.code : '') + (prompt.status === '已启用' ? '' : ' · ' + prompt.status)"
                :value="prompt.id" :disabled="prompt.status !== '已启用' && prompt.id !== form.prompt_config_id" />
            </el-select>
            <div v-if="form.prompt_config_id && !selectedPrompt" class="binding-note warning-note">已绑定的 Prompt 不存在，请清除或重新选择。</div>
            <div v-if="selectedPrompt" class="prompt-detail">
              <span>{{ selectedPrompt.description || '暂无说明' }}</span>
              <span v-if="selectedPrompt.status !== '已启用'" class="warning-note">该 Prompt 已停用，不会生效。</span>
              <details v-if="selectedPrompt.content"><summary>查看 Prompt 正文</summary><pre>{{ selectedPrompt.content }}</pre></details>
            </div>
            <div class="binding-note">启用的 Prompt 会作为角色指令；下方补充指令会追加在其后。</div>
          </el-form-item>
          <el-form-item label="Agent 补充指令"
            ><el-input
              v-model="form.prompt"
              type="textarea"
              :rows="4"
              placeholder="可补充此 Agent 的具体职责与要求" /></el-form-item>
          <el-form-item label="绑定 Skill（可多选）">
            <ConfigBindingPicker v-model="form.skill_config_ids" label="Skill" :items="skillOptions" />
          </el-form-item>
          <el-form-item label="绑定 Tools（可多选）">
            <ConfigBindingPicker v-model="form.tool_config_ids" label="Tools" :items="toolOptions" />
            <div class="binding-note">工具绑定目前仅保存角色配置，自动工具调用尚未接入。</div>
            <div v-if="form.tools?.length" class="binding-note">历史工具标签：{{ form.tools.join('、') }}（仅保留原数据）</div>
          </el-form-item
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
              <el-input-number v-model="form.extra.timeout_seconds" :min="5" :max="3600" :step="5" :precision="0" />
              <div class="binding-note">可设置 5–3600 秒；供应商或网关可能另有超时限制。</div>
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
          v-if="['prompts', 'skills', 'tools'].includes(section)"
          :label="section === 'prompts' ? 'Prompt 正文' : section === 'skills' ? 'Skill 内容' : '工具用途与约束'"
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
import ConfigBindingPicker from '../components/ConfigBindingPicker.vue'
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
  skillOptions = ref([]),
  toolOptions = ref([])
const selectedPrompt = computed(() => promptOptions.value.find((item) => item.id === form.value.prompt_config_id))
const roleRecommendations = [
  { match: /产品经理|产品负责人|product/i, prompt: 'app-product-manager', skills: ['app-requirements'], tools: ['app-document-reader'] },
  { match: /架构|architect/i, prompt: 'app-architect', skills: ['app-api-contract'], tools: ['app-workspace-files', 'app-document-reader'] },
  { match: /前端|frontend|front.end/i, prompt: 'app-frontend-developer', skills: ['app-frontend-implementation', 'app-accessibility'], tools: ['app-workspace-files', 'app-browser-preview', 'app-code-runner'] },
  { match: /后端|backend|back.end/i, prompt: 'app-backend-developer', skills: ['app-api-contract', 'app-backend-implementation'], tools: ['app-workspace-files', 'app-api-client', 'app-code-runner'] },
  { match: /移动|mobile|android|ios/i, prompt: 'app-mobile-developer', skills: ['app-interaction-spec', 'app-accessibility'], tools: ['app-workspace-files', 'app-code-runner'] },
  { match: /测试|质保|\bqa\b|test/i, prompt: 'app-qa-engineer', skills: ['app-qa-acceptance'], tools: ['app-browser-preview', 'app-api-client', 'app-code-runner'] },
  { match: /交互|用户体验|设计师|\bux\b|\bui\b/i, prompt: 'app-ux-designer', skills: ['app-interaction-spec', 'app-accessibility'], tools: ['app-design-assets', 'app-browser-preview'] }
]
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
    skill_config_ids: [],
    tool_config_ids: []
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
      ;[modelOptions.value, promptOptions.value, skillOptions.value, toolOptions.value] = await Promise.all([
        api.config('models'),
        api.config('prompts'),
        api.config('skills'),
        api.config('tools')
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
        skill_config_ids: x.skill_config_ids || [],
        tool_config_ids: x.tool_config_ids || []
      }
    : blank()
  form.value.category = section.value
  dialog.value = true
}
function syncModelName(id) {
  form.value.model_name = modelOptions.value.find((model) => model.id === id)?.model_name || ''
}
function modelBinding(agent) {
  const model = modelOptions.value.find((item) => item.id === agent.model_config_id)
  return model ? model.name + (model.status === '已启用' ? '' : '（' + model.status + '）') : agent.model_config_id ? '模型已删除' : agent.model_name || '未绑定'
}
function promptBinding(agent) {
  if (!agent.prompt_config_id) return agent.prompt ? '自定义补充指令' : '未绑定'
  const prompt = promptOptions.value.find((item) => item.id === agent.prompt_config_id)
  return prompt ? prompt.name + (prompt.status === '已启用' ? '' : '（' + prompt.status + '）') : 'Prompt 已删除'
}
function bindingSummary(ids, options) {
  if (!ids?.length) return '未绑定'
  return ids.map((id) => {
    const item = options.find((option) => option.id === id)
    return item ? item.name + (item.status === '已启用' ? '' : '（' + item.status + '）') : '#' + id + '（已删除）'
  }).join('、')
}
function applyRoleRecommendation() {
  const recommendation = roleRecommendations.find((item) => item.match.test(form.value.role || '')) ||
    roleRecommendations.find((item) => item.match.test(form.value.name || ''))
  if (!recommendation) return ElMessage.warning('未识别出开发角色，请填写角色名称或手动选择配置')
  const findEnabled = (items, code) => items.find((item) => item.code === code && item.status === '已启用')
  let added = 0
  if (!form.value.prompt_config_id) {
    const prompt = findEnabled(promptOptions.value, recommendation.prompt)
    if (prompt) { form.value.prompt_config_id = prompt.id; added++ }
  }
  if (!form.value.skill_config_ids.length) {
    form.value.skill_config_ids = recommendation.skills.map((code) => findEnabled(skillOptions.value, code)?.id).filter(Boolean)
    added += form.value.skill_config_ids.length
  }
  if (!form.value.tool_config_ids.length) {
    form.value.tool_config_ids = recommendation.tools.map((code) => findEnabled(toolOptions.value, code)?.id).filter(Boolean)
    added += form.value.tool_config_ids.length
  }
  if (added) ElMessage.success('已补充 ' + added + ' 项推荐，请确认后保存')
  else ElMessage.warning('已有绑定或推荐配置尚未启用，请手动调整')
}
async function save() {
  if (!form.value.name.trim()) return ElMessage.warning('请填写名称')
  if (section.value === 'models' && (!Number.isInteger(form.value.extra.timeout_seconds) ||
      form.value.extra.timeout_seconds < 5 || form.value.extra.timeout_seconds > 3600)) {
    return ElMessage.warning('请求超时请输入 5 至 3600 秒的整数')
  }
  try {
    if (section.value === 'agents')
      await api.saveAgent({
        ...form.value,
        temperature: Number(form.value.temperature ?? 0.3),
        tools: form.value.tools || []
      })
    else await api.saveConfig({ ...form.value, category: section.value })
    ElMessage.success('配置已保存')
    dialog.value = false
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败，请检查后端服务')
  }
}
async function toggle(x) {
  if (togglingId.value !== null) return
  togglingId.value = x.id
  try {
    const updated = section.value === 'agents'
      ? await api.saveAgent({ ...x, enabled: !x.enabled, status: x.enabled ? '离线' : '在线',
          tools: x.tools || [], skill_config_ids: x.skill_config_ids || [], tool_config_ids: x.tool_config_ids || [] })
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
.config-form { max-height: 65vh; overflow-y: auto; overflow-x: hidden; padding-right: 8px; }
.binding-note { margin-top: 5px; color: var(--muted); font-size: 12px; line-height: 1.5; }
.warning-note { color: var(--orange); }
.agent-binding-title { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 12px 0 18px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
.agent-binding-title small { display: block; margin-top: 4px; color: var(--muted); }
.prompt-detail { width: 100%; margin-top: 8px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; line-height: 1.5; }
.prompt-detail span { display: block; }
.prompt-detail summary { margin-top: 5px; color: var(--cyan); cursor: pointer; }
.prompt-detail pre { max-height: 180px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; color: var(--muted); }
.card-state { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.agent-bindings { display: grid; gap: 5px; margin: 8px 0 12px; font-size: 12px; }
.agent-bindings div { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 8px; }
.agent-bindings span { color: var(--muted); }
.agent-bindings b { font-weight: 400; overflow-wrap: anywhere; }
.knowledge-actions, .knowledge-document { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.knowledge-actions { justify-content: flex-start; margin-bottom: 16px; }
.knowledge-document, .knowledge-hit { padding: 10px 0; border-bottom: 1px solid var(--line); }
.knowledge-document small { margin-left: 8px; }
.knowledge-results { max-height: 240px; overflow: auto; margin: 14px 0; }
.knowledge-hit p { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--muted); }
</style>
