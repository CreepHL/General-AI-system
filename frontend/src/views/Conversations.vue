<template>
  <div class="conversation-page">
    <aside class="conversation-list">
      <div class="list-header">
        <div>
          <span class="section-kicker">AI WORKSPACE</span>
          <span class="history-heading">最近会话</span>
        </div>
        <el-button type="primary" round @click="openNew()">＋ 新建</el-button>
      </div>
      <el-input v-model="search" clearable placeholder="搜索对话或任务" class="history-search" />
      <div class="history-scroll">
        <div class="history-label">
          最近任务 <span>{{ filteredTasks.length }}</span>
        </div>
        <div v-for="group in taskGroups" :key="group.label" class="history-group">
          <div class="history-group-label">{{ group.label }}</div>
          <button
            v-for="task in group.tasks"
            :key="task.id"
            class="history-item"
            :class="{ selected: selected?.id === task.id }"
            @click="selectTask(task)"
          >
            <span class="history-icon">{{ task.target_type === 'team' ? '团' : '智' }}</span>
            <span class="history-copy">
              <strong>{{ task.title }}</strong>
              <small>{{ task.target_name || '未指定执行对象' }} · {{ task.status }}</small>
            </span>
          </button>
        </div>
        <div v-if="!filteredTasks.length" class="history-empty">
          {{ loading ? '正在加载…' : search ? '没有匹配的任务' : '还没有任务，点击新建开始' }}
        </div>
      </div>
    </aside>

    <section class="conversation-main" :class="{ 'preview-hidden': selected?.workflow?.app_mode && !previewVisible }">
      <template v-if="!selected">
        <div class="welcome">
          <div class="welcome-mark">✳</div>
          <div class="section-kicker">CREATE WITH YOUR AI TEAM</div>
          <h1>今天想完成什么？</h1>
          <p>描述你的目标，选择智能体或团队，开始一项新任务。</p>
          <div class="welcome-composer">
            <el-input
              v-model="draft"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 7 }"
              placeholder="例如：帮我梳理产品需求，并给出实施计划…"
              @keydown.ctrl.enter.prevent="openNew(draft)"
            />
            <div v-if="pendingFiles.length || pendingConnectorCodes.length" class="composer-chips">
              <span
                v-for="(file, index) in pendingFiles"
                :key="file.name + index"
                class="composer-chip"
              >
                📎 {{ file.name }}
                <button type="button" aria-label="移除附件" @click="pendingFiles.splice(index, 1)">
                  ×
                </button>
              </span>
              <span v-for="code in pendingConnectorCodes" :key="code" class="composer-chip"
                >⌁ {{ connectorName(code) }}</span
              >
            </div>
            <div class="composer-tools">
              <div class="composer-start">
                <el-dropdown trigger="click" @command="handlePlusCommand">
                  <button class="add-button" type="button" aria-label="添加附件或工具连接器">
                    ＋
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="attachment">📎 上传附件</el-dropdown-item>
                      <el-dropdown-item command="connectors">⌁ 工具连接器</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <span>可以先写下任务目标，再选择执行对象</span>
              </div>
              <el-button type="primary" round @click="openNew(draft)"
                >创建任务 <span aria-hidden="true">↗</span></el-button
              >
            </div>
          </div>
          <div class="suggestions">
            <button v-for="idea in suggestions" :key="idea" @click="openNew(idea)">
              {{ idea }} ↗
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <header class="conversation-header">
          <div>
            <span class="section-kicker">{{
              selected.target_type === 'team' ? '团队任务' : '智能体任务'
            }}</span>
            <h2>{{ selected.title }}</h2>
            <p>
              {{ selected.target_name }} · {{ selected.collaboration_mode }} · {{ selected.status }}
            </p>
          </div>
          <div class="header-actions">
            <el-button
              v-if="selected.status === '待执行'"
              type="primary"
              plain
              :loading="starting"
              @click="startSelected"
              >开始任务</el-button
            >
            <el-button v-if="canRebuildApp" type="primary" plain :loading="starting"
              :disabled="sending" @click="rebuildSelectedApp">按原需求重新生成预览</el-button>
            <label v-if="selected.workflow?.app_mode" class="preview-toggle"><span>预览</span>
              <el-switch v-model="previewVisible" aria-label="显示应用预览" @change="savePreviewVisibility" />
            </label>
            <el-button @click="openNew()">＋ 新建</el-button>
          </div>
        </header>
        <div v-if="selected.collaboration_mode === '流程图编排'" class="saved-flow">
          <strong>执行流程</strong>
          <template v-for="(node, index) in selected.workflow?.nodes || []" :key="node.agent_id">
            <span v-if="index" class="saved-flow-arrow">→</span>
            <span class="saved-flow-node">{{ agents.find((agent) => agent.id === node.agent_id)?.name || '智能体 #' + node.agent_id }}</span>
          </template>
        </div>
        <div class="conversation-workspace" :class="{ 'with-app': selected.workflow?.app_mode && previewVisible }">
        <div ref="messageList" class="message-list">
          <div v-if="!messages.length && selected.description" class="message-row mine">
            <div class="message-bubble">{{ selected.description }}</div>
          </div>
          <div
            v-for="message in messages"
            :key="message.id ?? message.streamKey"
            class="message-row"
            :class="{ mine: message.role === 'user' }"
          >
            <div class="message-bubble">
              <strong v-if="message.agent_name" class="message-agent">{{
                message.agent_name
              }}</strong>
              {{ message.content }}<span v-if="message.streaming" class="stream-cursor">▍</span>
            </div>
          </div>
          <div v-if="selected.result" class="message-row">
            <div class="message-bubble result">
              <strong>任务状态</strong><br />{{ selected.result }}
            </div>
          </div>
          <div v-if="attachments.length" class="attachment-section">
            <div class="section-kicker">任务附件</div>
            <button
              v-for="item in attachments"
              :key="item.id"
              class="attachment-item"
              @click="downloadAttachment(item)"
            >
              📎 {{ item.filename }} <small>{{ formatSize(item.size) }} · 下载</small>
            </button>
          </div>
          <div
            v-if="!messages.length && !selected.description && !selected.result"
            class="empty-conversation"
          >
            任务已创建。发送一条消息，补充你的目标或要求。
          </div>
        </div>
        <section v-if="selected.workflow?.app_mode && previewVisible" class="app-preview">
          <div class="app-preview-toolbar">
            <div>
              <strong>{{ appArtifact?.title || '应用预览' }}</strong>
              <small v-if="appArtifact">版本 v{{ appArtifact.version }} · {{ selected.status === '生成失败' ? '本轮生成失败，保留上一可用版' : previewError || '可操作预览' }}</small>
              <small v-else>{{ selected.status === '生成失败' ? '生成失败，可点击顶部按钮重试' : '等待生成应用' }}</small>
            </div>
            <div class="app-preview-actions">
              <el-select v-if="appArtifact" v-model="previewVersion" size="small" style="width: 112px" @change="showAppVersion">
                <el-option v-for="item in appVersions" :key="item.version" :label="'版本 v' + item.version" :value="item.version" />
              </el-select>
              <el-button v-if="appArtifact" size="small" @click="reloadPreview">刷新</el-button>
              <el-button v-if="appArtifact && previewVersion !== appVersions[0]?.version" size="small" @click="restoreAppVersion">恢复此版</el-button>
            </div>
          </div>
          <iframe v-if="appArtifact" :key="previewKey" ref="appFrame" class="app-frame"
            :srcdoc="previewDocument" sandbox="allow-scripts" referrerpolicy="no-referrer"
            title="生成应用的隔离预览" />
          <div v-else class="app-preview-empty">
            {{ starting || sending ? '正在生成并校验应用，请稍候…' : '输入应用需求并发送，生成后可直接在这里使用。' }}
          </div>
          <p v-if="previewError" class="app-preview-error">预览运行异常：{{ previewError }}。可继续对话修复，上一版仍可恢复。</p>
        </section>
        </div>
        <div class="chat-composer">
          <el-input
            v-model="reply"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            placeholder="补充任务要求… Ctrl + Enter 发送"
            @keydown.ctrl.enter.prevent="sendMessage"
          />
          <div v-if="selected.workflow?.connector_codes?.length" class="composer-chips">
            <span
              v-for="code in selected.workflow.connector_codes"
              :key="code"
              class="composer-chip"
              >⌁ {{ connectorName(code) }}</span
            >
          </div>
          <div class="composer-tools">
            <div class="composer-start">
              <el-dropdown trigger="click" @command="handlePlusCommand">
                <button class="add-button" type="button" aria-label="添加附件或工具连接器">
                  ＋
                </button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="attachment">📎 上传附件</el-dropdown-item>
                    <el-dropdown-item command="connectors">⌁ 工具连接器</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <span>发送消息后，已绑定模型的智能体会回复。</span>
            </div>
            <el-button v-if="canRetry" text :loading="sending" @click="retryMessage"
              >重试上一条</el-button
            >
            <el-button
              type="primary"
              round
              :disabled="!reply.trim() || canRetry"
              :loading="sending"
              @click="sendMessage"
              >发送 ↗</el-button
            >
          </div>
        </div>
      </template>
    </section>

    <input ref="fileInput" class="visually-hidden" type="file" multiple @change="handleFiles" />
    <el-dialog v-model="connectorDialog" title="工具连接器" width="min(480px, 94vw)">
      <p class="connector-help">
        选择平台配置中已启用的工具。当前仅保存任务关联，执行需要后续接入。
      </p>
      <el-checkbox-group v-model="connectorSelection" class="connector-list">
        <el-checkbox v-for="tool in enabledTools" :key="tool.code" :value="tool.code">
          {{ tool.name }} <span class="connector-description">{{ tool.description }}</span>
        </el-checkbox>
      </el-checkbox-group>
      <el-empty v-if="!enabledTools.length" description="暂无已启用的工具，请先到平台配置添加" />
      <template #footer>
        <el-button @click="connectorDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingConnectors" @click="saveConnectors"
          >保存选择</el-button
        >
      </template>
    </el-dialog>

    <el-dialog v-model="newDialog" title="新建对话与任务" width="min(560px, 94vw)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="createTask">
        <el-form-item label="任务名称" required>
          <el-input
            v-model="form.title"
            maxlength="200"
            show-word-limit
            placeholder="给这项任务起个清晰的名字"
          />
        </el-form-item>
        <el-form-item label="执行方式" required>
          <el-radio-group v-model="form.target_type" @change="resetTargets">
            <el-radio-button value="agent">智能体</el-radio-button>
            <el-radio-button value="team">团队协作</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.target_type === 'agent'" label="选择智能体（可多选）" required>
          <el-select
            v-model="form.agent_ids"
            @change="syncWorkflow"
            multiple
            filterable
            collapse-tags
            :max-collapse-tags="2"
            placeholder="请选择一个或多个智能体"
            style="width: 100%"
          >
            <el-option
              v-for="item in availableTargets"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="选择团队" required>
          <el-select
            v-model="form.target_id"
            @change="syncWorkflow"
            filterable
            placeholder="请选择执行对象"
            style="width: 100%"
          >
            <el-option
              v-for="item in availableTargets"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="form.target_type === 'team' || form.agent_ids.length > 1"
          label="协作模式"
        >
          <el-select v-model="form.collaboration_mode" style="width: 100%">
            <el-option label="串行协作" value="串行" />
            <el-option label="并行协作" value="并行" />
            <el-option label="自由讨论" value="自由讨论" />
            <el-option label="流程图编排" value="流程图编排" />
          </el-select>
        </el-form-item>
        <div v-if="form.collaboration_mode === '流程图编排'" class="flow-editor">
          <div class="flow-editor-title">智能体执行流程</div>
          <p>拖动卡片调整先后顺序，箭头表示输出传递给下一位智能体。</p>
          <p v-if="!workflowAgents.length">请先选择智能体或团队。</p>
          <p v-else-if="workflowAgents.some((agent) => !agent.enabled)">所选团队包含未启用的智能体，需先调整团队。</p>
          <div v-if="workflowAgents.length" class="flow-canvas">
            <div class="flow-endpoint">开始</div>
            <template v-for="(node, index) in form.workflow.nodes" :key="node.agent_id">
              <span class="flow-arrow" aria-hidden="true">↓</span>
              <div class="flow-agent" draggable="true" :class="{ dragging: draggedNode === index }"
                @dragstart="dragStart($event, index)" @dragover.prevent @drop.prevent="dropNode(index)" @dragend="draggedNode = null">
                <span class="flow-handle" aria-hidden="true">⠿</span>
                <span class="flow-order">{{ index + 1 }}</span>
                <strong>{{ workflowAgents.find((agent) => agent.id === node.agent_id)?.name || '未知智能体' }}</strong>
                <small>{{ workflowAgents.find((agent) => agent.id === node.agent_id)?.role }}</small>
              </div>
            </template>
            <span class="flow-arrow" aria-hidden="true">↓</span>
            <div class="flow-endpoint">完成</div>
          </div>
        </div>
        <el-form-item label="使用知识库（可多选）">
          <el-select v-model="form.knowledge_ids" multiple filterable collapse-tags placeholder="可选：从知识库检索相关文档" style="width: 100%">
            <el-option v-for="base in knowledgeBases" :key="base.id" :label="base.name" :value="base.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始描述（可选）">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="补充背景、目标或交付要求；也可以创建后再发消息"
          />
        </el-form-item>
        <el-form-item label="生成可操作应用">
          <el-switch v-model="form.app_mode" />
          <span class="app-mode-help">开启后生成可在右侧直接使用的单页应用；后续消息用于修改同一应用。</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createTask">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const tasks = ref([])
const agents = ref([])
const teams = ref([])
const tools = ref([])
const knowledgeBases = ref([])
const messages = ref([])
const attachments = ref([])
const pendingFiles = ref([])
const pendingConnectorCodes = ref([])
const connectorSelection = ref([])
const connectorDialog = ref(false)
const savingConnectors = ref(false)
const uploading = ref(false)
const fileInput = ref(null)
const selected = ref(null)
const messageList = ref(null)
const appFrame = ref(null)
const appArtifact = ref(null)
const appVersions = ref([])
const previewVersion = ref(null)
const previewError = ref('')
const previewKey = ref(0)
const previewVisible = ref(true)
const search = ref('')
const draft = ref('')
const reply = ref('')
const loading = ref(false)
const creating = ref(false)
const sending = ref(false)
const starting = ref(false)
const newDialog = ref(false)
const draggedNode = ref(null)
const suggestions = ['梳理产品需求', '分析项目架构', '制定测试计划']
const form = ref({
  title: '',
  description: '',
  target_type: 'agent',
  target_id: null,
  agent_ids: [],
  knowledge_ids: [],
  app_mode: true,
  collaboration_mode: '串行',
  workflow: { nodes: [] }
})
const availableTargets = computed(() =>
  form.value.target_type === 'team' ? teams.value : agents.value.filter((agent) => agent.enabled)
)
const workflowAgents = computed(() => {
  const ids = form.value.target_type === 'team'
    ? teams.value.find((team) => team.id === form.value.target_id)?.agent_ids || []
    : form.value.agent_ids
  return ids.map((id) => agents.value.find((agent) => agent.id === id)).filter(Boolean)
})
function syncWorkflow() {
  const ids = workflowAgents.value.map((agent) => agent.id)
  const retained = (form.value.workflow?.nodes || []).filter((node) => ids.includes(node.agent_id))
  const seen = new Set(retained.map((node) => node.agent_id))
  form.value.workflow = { nodes: [...retained, ...ids.filter((id) => !seen.has(id)).map((agent_id) => ({ agent_id }))] }
}
function dragStart(event, index) {
  draggedNode.value = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(index))
}
function dropNode(index) {
  if (draggedNode.value === null) return
  const nodes = [...form.value.workflow.nodes]
  nodes.splice(index, 0, nodes.splice(draggedNode.value, 1)[0])
  form.value.workflow = { nodes }
  draggedNode.value = null
}
const enabledTools = computed(() =>
  tools.value.filter((tool) => tool.status === '已启用' && tool.code)
)
const canRetry = computed(() => messages.value.at(-1)?.role === 'user')
const canRebuildApp = computed(() => selected.value && !appArtifact.value &&
  (messages.value.some((message) => message.role === 'user') || selected.value.description?.trim()) &&
  (!selected.value.workflow?.app_mode || selected.value.status === '生成失败'))
function readAppState(taskId) {
  try { return JSON.parse(localStorage.getItem('general-ai-app-state-' + taskId) || '{}') }
  catch { return {} }
}
const previewDocument = computed(() => {
  if (!appArtifact.value || !selected.value) return ''
  const app = appArtifact.value
  const state = JSON.stringify(readAppState(selected.value.id)).replace(/</g, '\\u003c')
  const bootstrap = 'const state=' + state + ';window.appStore={get:key=>state[key],set:(key,value)=>{state[key]=value;parent.postMessage({type:"app-store-set",key,value},"*")}};window.addEventListener("error",e=>parent.postMessage({type:"app-preview-error",message:e.message},"*"));window.addEventListener("unhandledrejection",e=>parent.postMessage({type:"app-preview-error",message:String(e.reason)},"*"));'
  const scriptEnd = '</scr' + 'ipt>'
  return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'nonce-app-preview\'; style-src \'unsafe-inline\'; img-src data: blob:; connect-src \'none\'; form-action \'none\'; base-uri \'none\'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>' + app.css + '</style></head><body>' + app.html + '<script nonce="app-preview">' + bootstrap + scriptEnd + '<script nonce="app-preview">' + app.javascript + scriptEnd + '</body></html>'
})
function onAppMessage(event) {
  if (!appFrame.value || event.source !== appFrame.value.contentWindow || !selected.value?.workflow?.app_mode) return
  const data = event.data
  if (!data || typeof data !== 'object') return
  if (data.type === 'app-preview-error') {
    previewError.value = String(data.message || '未知错误').slice(0, 200)
  } else if (data.type === 'app-store-set' && typeof data.key === 'string' && data.key.length <= 100) {
    try {
      const state = readAppState(selected.value.id)
      state[data.key] = data.value
      const encoded = JSON.stringify(state)
      if (encoded.length <= 100000) localStorage.setItem('general-ai-app-state-' + selected.value.id, encoded)
    } catch {
      previewError.value = '应用数据无法保存到本机浏览器'
    }
  }
}
function reloadPreview() { previewError.value = ''; previewKey.value++ }
function readPreviewVisibility(taskId) {
  try { return localStorage.getItem('general-ai-preview-visible-' + taskId) !== 'off' }
  catch { return true }
}
function savePreviewVisibility(value) {
  if (!selected.value) return
  try { localStorage.setItem('general-ai-preview-visible-' + selected.value.id, value ? 'on' : 'off') }
  catch { /* Keep this tab's choice when browser storage is unavailable. */ }
  if (value) reloadPreview()
}
async function showAppVersion(version) {
  if (!selected.value) return
  const taskId = selected.value.id
  try {
    const artifact = await api.taskAppVersion(taskId, version)
    if (selected.value?.id === taskId) { appArtifact.value = artifact; reloadPreview() }
  } catch { ElMessage.error('读取应用版本失败') }
}
async function restoreAppVersion() {
  if (!selected.value || !previewVersion.value) return
  try {
    const artifact = await api.restoreTaskAppVersion(selected.value.id, previewVersion.value)
    appArtifact.value = artifact
    appVersions.value = await api.taskAppVersions(selected.value.id)
    previewVersion.value = artifact.version
    selected.value.status = '可预览'
    selected.value.result = ''
    reloadPreview()
    ElMessage.success('旧版本已恢复为最新版本')
  } catch { ElMessage.error('恢复版本失败') }
}
function streamEvent(taskId) {
  return (event) => {
    if (selected.value?.id !== taskId) return
    if (event.type === 'user_message') {
      messages.value.push(event.message)
      reply.value = ''
    } else if (event.type === 'delta') {
      const key = 'task-' + taskId + '-agent-' + event.agent_index
      let bubble = messages.value.find((item) => item.streamKey === key)
      if (!bubble) {
        bubble = { streamKey: key, role: 'assistant', agent_name: event.agent_name, content: '', streaming: true }
        messages.value.push(bubble)
      }
      bubble.content += event.content
    } else if (event.type === 'message') {
      const key = 'task-' + taskId + '-agent-' + event.agent_index
      const index = messages.value.findIndex((item) => item.streamKey === key)
      if (index >= 0) messages.value.splice(index, 1, event.message)
      else messages.value.push(event.message)
    } else if (event.type === 'status') {
      selected.value.status = event.status
      if (selected.value.workflow?.app_mode) selected.value.result = ''
    } else if (event.type === 'error' && selected.value.workflow?.app_mode) {
      selected.value.status = '生成失败'
      selected.value.result = event.detail
    } else if (event.type === 'artifact') {
      appArtifact.value = event.artifact
      previewVersion.value = event.artifact.version
      appVersions.value.unshift({ id: event.artifact.id, version: event.artifact.version, title: event.artifact.title })
      selected.value.status = '可预览'
      selected.value.result = ''
      reloadPreview()
    }
    nextTick(() => { if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight })
  }
}
async function recoverStream(taskId) {
  if (selected.value?.id !== taskId) return
  const [messageResult, taskResult, appResult, versionResult] = await Promise.allSettled([
    api.taskMessages(taskId), api.tasks(), api.taskApp(taskId), api.taskAppVersions(taskId)
  ])
  if (selected.value?.id !== taskId) return
  if (messageResult.status === 'fulfilled') messages.value = messageResult.value
  if (taskResult.status === 'fulfilled') {
    tasks.value = taskResult.value
    selected.value = tasks.value.find((item) => item.id === taskId) || selected.value
  }
  if (appResult.status === 'fulfilled' && selected.value.workflow?.app_mode) {
    appArtifact.value = appResult.value
    previewVersion.value = appResult.value?.version || null
    reloadPreview()
  }
  if (versionResult.status === 'fulfilled') appVersions.value = versionResult.value
}
const filteredTasks = computed(() =>
  tasks.value.filter((task) =>
    (task.title + ' ' + task.target_name).toLowerCase().includes(search.value.trim().toLowerCase())
  )
)
const taskGroups = computed(() =>
  [
    { label: '团队任务', tasks: filteredTasks.value.filter((task) => task.target_type === 'team') },
    {
      label: '智能体对话',
      tasks: filteredTasks.value.filter((task) => task.target_type !== 'team')
    }
  ].filter((group) => group.tasks.length)
)

onMounted(async () => {
  window.addEventListener('message', onAppMessage)
  loading.value = true
  try {
    const [taskRows, agentRows, teamRows, toolRows, knowledgeRows] = await Promise.all([
      api.tasks(),
      api.agents(),
      api.teams(),
      api.config('tools'),
      api.config('knowledge')
    ])
    tasks.value = taskRows
    agents.value = agentRows
    teams.value = teamRows
    tools.value = toolRows
    knowledgeBases.value = knowledgeRows.filter((base) => base.status === '已启用')
  } catch {
    ElMessage.error('加载失败，请检查后端服务')
  } finally {
    loading.value = false
  }
})
onUnmounted(() => window.removeEventListener('message', onAppMessage))

function openNew(description = '') {
  form.value = {
    title: '',
    description,
    target_type: 'agent',
    target_id: null,
    agent_ids: [],
    knowledge_ids: [],
    app_mode: true,
    collaboration_mode: '串行',
    workflow: { nodes: [] }
  }
  newDialog.value = true
}

function resetTargets() {
  form.value.target_id = null
  form.value.agent_ids = []
  form.value.workflow = { nodes: [] }
}

async function selectTask(task) {
  selected.value = task
  previewVisible.value = readPreviewVisibility(task.id)
  messages.value = []
  attachments.value = []
  appArtifact.value = null
  appVersions.value = []
  previewVersion.value = null
  previewError.value = ''
  try {
    const [taskMessages, taskAttachments, artifact, versions] = await Promise.all([
      api.taskMessages(task.id),
      api.taskAttachments(task.id),
      task.workflow?.app_mode ? api.taskApp(task.id) : Promise.resolve(null),
      task.workflow?.app_mode ? api.taskAppVersions(task.id) : Promise.resolve([])
    ])
    if (selected.value?.id !== task.id) return
    messages.value = taskMessages
    attachments.value = taskAttachments
    appArtifact.value = artifact
    appVersions.value = versions
    previewVersion.value = artifact?.version || null
    await nextTick()
    if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
  } catch {
    ElMessage.error('读取消息失败')
  }
}

async function createTask() {
  const title = form.value.title.trim()
  const selectedAgents = agents.value.filter((agent) => form.value.agent_ids.includes(agent.id))
  const target =
    form.value.target_type === 'team'
      ? teams.value.find((team) => team.id === form.value.target_id)
      : selectedAgents[0]
  if (!title || !target) return ElMessage.warning('请填写任务名称并选择执行对象')
  if (form.value.collaboration_mode === '流程图编排' && !workflowAgents.value.length) {
    return ElMessage.warning('流程图编排至少需要一个已启用的智能体')
  }
  if (form.value.collaboration_mode === '流程图编排' && workflowAgents.value.some((agent) => !agent.enabled)) {
    return ElMessage.warning('团队中包含未启用的智能体，请先调整团队或启用智能体')
  }
  if (form.value.collaboration_mode === '流程图编排') syncWorkflow()
  creating.value = true
  try {
    const task = await api.createTask({
      title,
      description: form.value.description.trim(),
      target_type: form.value.target_type,
      target_id: target.id,
      target_name:
        form.value.target_type === 'agent'
          ? selectedAgents.map((agent) => agent.name).join('、')
          : target.name,
      team_id: form.value.target_type === 'team' ? target.id : null,
      collaboration_mode:
        form.value.collaboration_mode === '流程图编排' || form.value.target_type === 'team' || selectedAgents.length > 1
          ? form.value.collaboration_mode
          : '串行',
      workflow:
        form.value.target_type === 'agent'
          ? {
              agent_ids: selectedAgents.map((agent) => agent.id),
              connector_codes: pendingConnectorCodes.value,
              knowledge_ids: form.value.knowledge_ids,
              app_mode: form.value.app_mode,
              ...(form.value.collaboration_mode === '流程图编排' ? { nodes: form.value.workflow.nodes } : {})
            }
          : { connector_codes: pendingConnectorCodes.value, knowledge_ids: form.value.knowledge_ids, app_mode: form.value.app_mode,
              ...(form.value.collaboration_mode === '流程图编排' ? { nodes: form.value.workflow.nodes } : {}) }
    })
    tasks.value.unshift(task)
    window.dispatchEvent(new Event('tasks-changed'))
    draft.value = ''
    newDialog.value = false
    await selectTask(task)
    if (pendingFiles.value.length) {
      const files = [...pendingFiles.value]
      pendingFiles.value = []
      await uploadFiles(task.id, files)
    }
    pendingConnectorCodes.value = []
    ElMessage.success('任务已创建')
    if (task.description.trim()) startSelected()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败，请检查后端服务')
  } finally {
    creating.value = false
  }
}

async function sendMessage() {
  const content = reply.value.trim()
  if (!content || !selected.value || sending.value || canRetry.value) return
  sending.value = true
  try {
    const taskId = selected.value.id
    const outcome = await api.streamTaskMessage(taskId, content, streamEvent(taskId))
    if (selected.value?.workflow?.app_mode && !outcome.artifactReceived) throw new Error('未收到完整的应用产物，请重试')
    const nextStatus = selected.value?.workflow?.app_mode ? '可预览' : '进行中'
    if (selected.value?.id === taskId) selected.value.status = nextStatus
    tasks.value = tasks.value.map((item) =>
      item.id === taskId ? { ...item, status: nextStatus } : item
    )
    window.dispatchEvent(new Event('tasks-changed'))
    await nextTick()
    if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
  } catch (error) {
    const taskId = selected.value?.id
    if (taskId) {
      await recoverStream(taskId)
      if (messages.value.at(-1)?.role === 'user') reply.value = ''
    }
    ElMessage.error(error.message || '发送失败，请检查模型配置和后端服务')
  } finally {
    sending.value = false
  }
}

async function retryMessage() {
  if (!selected.value || !canRetry.value || sending.value) return
  sending.value = true
  try {
    const taskId = selected.value.id
    const outcome = await api.streamTaskRetry(taskId, streamEvent(taskId))
    if (selected.value?.workflow?.app_mode && !outcome.artifactReceived) throw new Error('未收到完整的应用产物，请重试')
    if (selected.value?.id === taskId && selected.value.workflow?.app_mode) selected.value.status = '可预览'
    window.dispatchEvent(new Event('tasks-changed'))
    await nextTick()
    if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
  } catch (error) {
    await recoverStream(selected.value.id)
    ElMessage.error(error.message || '重试失败')
  } finally {
    sending.value = false
  }
}

async function rebuildSelectedApp() {
  if (!canRebuildApp.value || starting.value || sending.value) return
  const taskId = selected.value.id
  starting.value = true
  selected.value.workflow = { ...(selected.value.workflow || {}), app_mode: true }
  try {
    const outcome = await api.streamTaskAppRebuild(taskId, streamEvent(taskId))
    if (!outcome.artifactReceived) throw new Error('未收到完整的应用产物，请重试')
    await recoverStream(taskId)
    ElMessage.success('应用已生成，可在右侧操作预览')
  } catch (error) {
    await recoverStream(taskId)
    ElMessage.error(error.message || '重新生成失败')
  } finally {
    starting.value = false
  }
}

async function startSelected() {
  if (!selected.value) return
  starting.value = true
  try {
    const taskId = selected.value.id
    const outcome = await api.streamTaskStart(taskId, streamEvent(taskId))
    if (selected.value?.workflow?.app_mode && !outcome.artifactReceived) throw new Error('未收到完整的应用产物，请重试')
    if (selected.value?.id === taskId) {
      const nextStatus = selected.value.workflow?.app_mode ? '可预览' : '进行中'
      selected.value.status = nextStatus
      tasks.value = tasks.value.map((item) => item.id === taskId ? { ...item, status: nextStatus } : item)
    }
    window.dispatchEvent(new Event('tasks-changed'))
    ElMessage.success(selected.value?.workflow?.app_mode ? '应用已生成，可直接预览' : '智能体已回复')
  } catch (error) {
    await recoverStream(selected.value.id)
    ElMessage.error(error.message || '启动任务失败')
  } finally {
    starting.value = false
  }
}

function connectorName(code) {
  return tools.value.find((tool) => tool.code === code)?.name || code
}

function formatSize(bytes) {
  return bytes < 1024 * 1024
    ? Math.ceil(bytes / 1024) + ' KB'
    : (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function handlePlusCommand(command) {
  if (command === 'attachment') fileInput.value?.click()
  if (command === 'connectors') {
    connectorSelection.value = selected.value
      ? [...(selected.value.workflow?.connector_codes || [])]
      : [...pendingConnectorCodes.value]
    connectorDialog.value = true
  }
}

async function handleFiles(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  const valid = files.filter((file) => {
    if (file.size <= 10 * 1024 * 1024) return true
    ElMessage.warning(file.name + ' 超过 10 MB，未添加')
    return false
  })
  if (!valid.length) return
  if (!selected.value) {
    pendingFiles.value.push(...valid)
    ElMessage.success('附件已添加，创建任务后会上传')
  } else {
    await uploadFiles(selected.value.id, valid)
  }
}

async function uploadFiles(taskId, files) {
  if (uploading.value) return
  uploading.value = true
  let failures = 0
  for (const file of files) {
    try {
      const item = await api.uploadTaskAttachment(taskId, file)
      if (selected.value?.id === taskId) attachments.value.push(item)
    } catch {
      failures++
    }
  }
  uploading.value = false
  if (failures) ElMessage.error(failures + ' 个附件上传失败')
  else ElMessage.success('附件上传成功')
}

async function downloadAttachment(item) {
  if (!selected.value) return
  try {
    const blob = await api.downloadTaskAttachment(selected.value.id, item.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = item.filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    ElMessage.error('下载附件失败')
  }
}

async function saveConnectors() {
  if (!selected.value) {
    pendingConnectorCodes.value = [...connectorSelection.value]
    connectorDialog.value = false
    return
  }
  savingConnectors.value = true
  try {
    const task = await api.updateTaskConnectors(selected.value.id, connectorSelection.value)
    selected.value = task
    tasks.value = tasks.value.map((item) => (item.id === task.id ? task : item))
    connectorDialog.value = false
    ElMessage.success('连接器选择已保存')
  } catch {
    ElMessage.error('保存连接器失败')
  } finally {
    savingConnectors.value = false
  }
}
</script>

<style scoped>
.conversation-page {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: calc(100vh - 148px);
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--panel);
}
.flow-editor { margin: 0 0 18px; padding: 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel2); }
.flow-editor-title { font-weight: 700; color: inherit; }
.flow-editor p { margin: 5px 0 13px; color: var(--muted); font-size: 12px; }
.flow-canvas { display: flex; flex-direction: column; align-items: center; max-height: 320px; overflow: auto; padding: 10px; border: 1px dashed var(--line); border-radius: 12px; background: var(--panel); }
.flow-endpoint { padding: 5px 18px; border-radius: 999px; color: var(--cyan); background: color-mix(in srgb, var(--cyan) 12%, var(--panel)); font-size: 12px; }
.flow-arrow { color: var(--cyan); font-size: 20px; line-height: 1.25; }
.flow-agent { display: flex; align-items: center; gap: 9px; width: min(100%, 450px); min-height: 48px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel2); color: inherit; cursor: grab; }
.flow-agent:active { cursor: grabbing; }
.flow-agent.dragging { opacity: .45; }
.flow-handle { color: var(--muted); font-size: 21px; }
.flow-order { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: color-mix(in srgb, var(--cyan) 16%, var(--panel)); color: var(--cyan); font-size: 12px; }
.flow-agent strong { font-size: 13px; }
.flow-agent small { margin-left: auto; color: var(--muted); font-size: 11px; }
.saved-flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 10px 24px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 12px; }
.saved-flow strong { margin-right: 4px; color: inherit; }
.saved-flow-node { padding: 5px 9px; border-radius: 8px; border: 1px solid var(--line); background: var(--panel2); color: inherit; }
.saved-flow-arrow { color: var(--cyan); }
.conversation-list {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-right: 1px solid var(--line);
  background: var(--panel2);
}
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 23px 18px 14px;
}
.list-header h2,
.conversation-header h2 {
  margin: 6px 0 0;
  font-size: 20px;
}
.history-heading {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  font-weight: 650;
}
.section-kicker {
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
}
.history-search {
  padding: 0 16px 18px;
}
.history-scroll {
  overflow: auto;
  flex: 1;
  padding: 0 10px 18px;
}
.history-label {
  display: flex;
  justify-content: space-between;
  margin: 5px 9px 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}
.history-group-label {
  margin: 14px 9px 5px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px 9px;
  border: 0;
  border-radius: 12px;
  text-align: left;
  color: inherit;
  background: transparent;
  cursor: pointer;
}
.history-item:hover,
.history-item.selected {
  background: color-mix(in srgb, var(--cyan) 12%, transparent);
}
.history-icon {
  display: grid;
  flex: 0 0 38px;
  height: 38px;
  place-items: center;
  border-radius: 10px;
  color: var(--cyan);
  background: color-mix(in srgb, var(--cyan) 13%, var(--panel));
  font-weight: 700;
}
.history-copy {
  display: block;
  min-width: 0;
}
.history-copy strong,
.history-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-copy strong {
  font-size: 13px;
}
.history-copy small {
  margin-top: 5px;
  color: var(--muted);
  font-size: 11px;
}
.history-empty {
  padding: 28px 10px;
  text-align: center;
  color: var(--muted);
  font-size: 12px;
}
.conversation-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.conversation-workspace {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 280px;
}
.conversation-workspace .message-list {
  min-width: 0;
}
.conversation-workspace.with-app .message-list {
  flex: 0 0 38%;
  padding: 18px;
  border-right: 1px solid var(--line);
}
.conversation-workspace.with-app .message-bubble {
  max-width: 100%;
}
.app-preview {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 340px;
  background: var(--panel);
}
.app-preview-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
}
.app-preview-toolbar strong, .app-preview-toolbar small {
  display: block;
}
.app-preview-toolbar small {
  color: var(--muted);
  margin-top: 3px;
}
.app-preview-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.preview-toggle { display: inline-flex; align-items: center; gap: 6px; margin: 0 8px; color: var(--muted); font-size: 13px; white-space: nowrap; }
.app-frame {
  flex: 1;
  width: 100%;
  min-height: 360px;
  border: 0;
  background: #fff;
}
.app-preview-empty {
  display: grid;
  flex: 1;
  place-items: center;
  padding: 24px;
  color: var(--muted);
  text-align: center;
}
.app-preview-error {
  margin: 0;
  padding: 8px 14px;
  color: #b42318;
  background: #fff1ef;
  font-size: 12px;
}
.app-mode-help {
  margin-left: 12px;
  color: var(--muted);
  font-size: 12px;
}
.welcome {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 22px 70px;
  text-align: center;
}
.welcome-mark {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  margin-bottom: 22px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--cyan) 15%, var(--panel));
  color: var(--cyan);
  font-size: 34px;
}
.welcome h1 {
  margin: 12px 0 8px;
  font-size: clamp(27px, 4vw, 42px);
}
.welcome p {
  margin: 0 0 30px;
  color: var(--muted);
  font-size: 14px;
}
.welcome-composer,
.chat-composer {
  width: min(100%, 760px);
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 19px;
  background: var(--panel);
  box-shadow: 0 14px 40px #12335212;
  text-align: left;
}
.welcome-composer :deep(.el-textarea__inner),
.chat-composer :deep(.el-textarea__inner) {
  border: 0;
  box-shadow: none !important;
  resize: none;
  background: transparent !important;
}
.composer-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}
.composer-start {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.add-button {
  width: 35px;
  height: 35px;
  flex: 0 0 35px;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: var(--panel2);
  color: var(--cyan);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}
.add-button:hover {
  border-color: var(--cyan);
}
.composer-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 9px 0 2px;
}
.composer-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 5px 9px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--panel2);
  color: var(--muted);
  font-size: 11px;
  overflow-wrap: anywhere;
}
.composer-chip button {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 16px;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}
.connector-help {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 12px;
}
.connector-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.connector-description {
  margin-left: 8px;
  color: var(--muted);
  font-size: 11px;
}
.attachment-section {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 9px;
  margin: 16px 0;
}
.attachment-item {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 9px 12px;
  background: var(--panel2);
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.attachment-item:hover {
  border-color: var(--cyan);
}
.attachment-item small {
  display: block;
  margin-top: 3px;
  color: var(--muted);
}
.composer-tools span {
  color: var(--muted);
  font-size: 11px;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 9px;
  margin-top: 16px;
}
.suggestions button {
  padding: 9px 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel2);
  color: inherit;
  cursor: pointer;
}
.suggestions button:hover {
  border-color: var(--cyan);
  color: var(--cyan);
}
.conversation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 19px 24px;
  border-bottom: 1px solid var(--line);
}
.conversation-header p {
  margin: 7px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.header-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.message-list {
  flex: 1;
  min-height: 250px;
  max-height: calc(100vh - 385px);
  overflow: auto;
  padding: 28px clamp(18px, 8%, 90px);
}
.message-row {
  display: flex;
  margin-bottom: 18px;
}
.message-row.mine {
  justify-content: flex-end;
}
.message-bubble {
  max-width: min(78%, 620px);
  padding: 13px 17px;
  border: 1px solid var(--line);
  border-radius: 16px 16px 16px 4px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--panel2);
  line-height: 1.6;
  font-size: 13px;
}
.mine .message-bubble {
  border-color: transparent;
  border-radius: 16px 16px 4px 16px;
  background: color-mix(in srgb, var(--cyan) 13%, var(--panel));
}
.message-bubble.result {
  color: var(--muted);
}
.message-agent {
  display: block;
  margin-bottom: 6px;
  color: var(--cyan);
  font-size: 11px;
}
.stream-cursor {
  color: var(--cyan);
  animation: stream-blink 1s steps(1) infinite;
}
@keyframes stream-blink {
  50% { opacity: 0; }
}
.empty-conversation {
  margin: 80px auto;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}
.chat-composer {
  margin: 0 auto 22px;
}
.conversation-main.preview-hidden .chat-composer {
  width: min(calc(100% - 48px), 1000px);
}
.conversation-main.preview-hidden .message-bubble {
  max-width: min(85%, 900px);
}
@media (max-width: 900px) {
  .conversation-page {
    grid-template-columns: 220px minmax(0, 1fr);
  }
  .chat-composer {
    width: calc(100% - 32px);
  }
  .conversation-workspace.with-app {
    flex-direction: column;
  }
  .conversation-workspace.with-app .message-list {
    flex: 0 0 auto;
    max-height: 220px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}
@media (max-width: 700px) {
  .conversation-page {
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 120px);
  }
  .conversation-list {
    max-height: 185px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .list-header {
    padding: 12px;
  }
  .list-header h2 {
    font-size: 16px;
  }
  .history-search {
    padding: 0 12px 8px;
  }
  .history-scroll {
    display: flex;
    gap: 6px;
    padding: 0 12px 10px;
  }
  .history-label,
  .history-empty {
    display: none;
  }
  .history-item {
    min-width: 155px;
    width: 155px;
  }
  .history-group {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .history-group-label {
    display: none;
  }
  .history-icon {
    display: none;
  }
  .welcome {
    padding: 36px 14px;
  }
  .conversation-header {
    padding: 14px;
    align-items: flex-start;
  }
  .header-actions {
    flex-direction: column;
  }
  .message-list {
    max-height: none;
  }
}
</style>
