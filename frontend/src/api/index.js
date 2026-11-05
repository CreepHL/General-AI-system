import axios from 'axios'
const http = axios.create({ baseURL: '/api', timeout: 15000 })
async function streamTask(path, body, onEvent) {
  const response = await fetch('/api' + path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || '请求失败（HTTP ' + response.status + '）')
  }
  if (!response.body) throw new Error('浏览器无法读取流式响应')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  let completed = false
  let artifactReceived = false
  function consume(block) {
    const line = block.split('\n').find((part) => part.startsWith('data:'))
    if (!line) return
    const event = JSON.parse(line.slice(5).trim())
    onEvent(event)
    if (event.type === 'artifact') artifactReceived = true
    if (event.type === 'error') throw new Error(event.detail)
    if (event.type === 'done') completed = true
  }
  while (true) {
    const { done, value } = await reader.read()
    pending += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n')
    let boundary
    while ((boundary = pending.indexOf('\n\n')) !== -1) {
      consume(pending.slice(0, boundary))
      pending = pending.slice(boundary + 2)
    }
    if (done) break
  }
  if (pending.trim()) consume(pending)
  if (!completed) throw new Error('流式连接中断，请重试上一条消息')
  return { artifactReceived }
}
export const api = {
  dashboard: () => http.get('/dashboard').then((r) => r.data),
  agents: () => http.get('/agents').then((r) => r.data),
  saveAgent: (x) =>
    x.id
      ? http.put(`/agents/${x.id}`, x).then((r) => r.data)
      : http.post('/agents', x).then((r) => r.data),
  deleteAgent: (id) => http.delete(`/agents/${id}`),
  teams: () => http.get('/teams').then((r) => r.data),
  saveTeam: (x) =>
    x.id
      ? http.put(`/teams/${x.id}`, x).then((r) => r.data)
      : http.post('/teams', x).then((r) => r.data),
  deleteTeam: (id) => http.delete(`/teams/${id}`),
  tasks: () => http.get('/tasks').then((r) => r.data),
  runningTaskCount: () => http.get('/tasks/running-count').then((r) => r.data.count),
  createTask: (x) => http.post('/tasks', x).then((r) => r.data),
  taskApp: (id) => http.get('/tasks/' + id + '/app').then((r) => r.data),
  taskAppState: (id) => http.get('/tasks/' + id + '/app/state').then((r) => r.data),
  saveTaskAppState: (id, key, value) => http.put('/tasks/' + id + '/app/state', { key, value }).then((r) => r.data),
  taskAppVersions: (id) => http.get('/tasks/' + id + '/app/versions').then((r) => r.data),
  taskAppVersion: (id, version) => http.get('/tasks/' + id + '/app/versions/' + version).then((r) => r.data),
  restoreTaskAppVersion: (id, version) => http.post('/tasks/' + id + '/app/versions/' + version + '/restore').then((r) => r.data),
  taskMessages: (id) => http.get('/tasks/' + id + '/messages').then((r) => r.data),
  sendTaskMessage: (id, content) =>
    http.post('/tasks/' + id + '/messages', { content }, { timeout: 0 }).then((r) => r.data),
  streamTaskMessage: (id, content, onEvent) =>
    streamTask('/tasks/' + id + '/messages/stream', { content }, onEvent),
  streamTaskRetry: (id, onEvent) => streamTask('/tasks/' + id + '/retry/stream', null, onEvent),
  streamTaskAppRebuild: (id, onEvent) => streamTask('/tasks/' + id + '/app/rebuild/stream', null, onEvent),
  streamTaskStart: (id, onEvent) => streamTask('/tasks/' + id + '/start/stream', null, onEvent),
  retryTaskMessage: (id) =>
    http.post('/tasks/' + id + '/retry', null, { timeout: 0 }).then((r) => r.data),
  testModel: (id, apiKey = '') =>
    http.post('/config/models/' + id + '/test', { api_key: apiKey }, { timeout: 0 }).then((r) => r.data),
  taskAttachments: (id) => http.get('/tasks/' + id + '/attachments').then((r) => r.data),
  uploadTaskAttachment: (id, file) => {
    const data = new FormData()
    data.append('file', file)
    return http.post('/tasks/' + id + '/attachments', data).then((r) => r.data)
  },
  downloadTaskAttachment: (id, attachmentId) =>
    http
      .get('/tasks/' + id + '/attachments/' + attachmentId, { responseType: 'blob' })
      .then((r) => r.data),
  updateTaskConnectors: (id, codes) =>
    http.put('/tasks/' + id + '/connectors', { codes }).then((r) => r.data),
  startTask: (id) =>
    http.post('/tasks/' + id + '/start', null, { timeout: 0 }).then((r) => r.data),
  config: (cat) => http.get(`/config/${cat}`).then((r) => r.data),
  saveConfig: (x) =>
    x.id
      ? http.put(`/config/${x.id}`, x).then((r) => r.data)
      : http.post('/config', x).then((r) => r.data),
  setConfigStatus: (id, status) => http.patch(`/config/${id}/status`, { status }).then((r) => r.data),
  deleteConfig: (id) => http.delete(`/config/${id}`),
  knowledgeDocuments: (id) => http.get('/knowledge/' + id + '/documents').then((r) => r.data),
  uploadKnowledgeDocument: (id, file) => {
    const data = new FormData()
    data.append('file', file)
    return http.post('/knowledge/' + id + '/documents', data, { timeout: 60000 }).then((r) => r.data)
  },
  deleteKnowledgeDocument: (id, documentId) => http.delete('/knowledge/' + id + '/documents/' + documentId),
  searchKnowledge: (query, knowledgeId) => http.get('/knowledge/search', { params: { q: query, knowledge_id: knowledgeId } }).then((r) => r.data),
  costs: () => http.get('/costs').then((r) => r.data)
}
