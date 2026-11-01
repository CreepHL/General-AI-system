# General AI System

借鉴 Atoms 多智能体产品的协作方式，使用 Vue 3 + FastAPI 实现的的通用 AI 应用平台原型。

## 技术栈
- Frontend: Vue 3, Vite, Vue Router, Pinia, Element Plus, ECharts
- Backend: FastAPI, SQLAlchemy 2, Pydantic
- Database: 默认 SQLite 开箱即用；可通过 `DATABASE_URL` 切换 MySQL

## 启动（Windows PowerShell）
后端：
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
API 文档：http://127.0.0.1:8000/docs

前端（Node.js 18+）：
```powershell
cd frontend
npm install
npm run dev
```
浏览器打开 http://localhost:5173。

首次启动自动创建 `backend/general_ai.db` 并写入演示数据。MySQL 示例：
`DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/general_ai_system?charset=utf8mb4`

## 页面功能
- 首页：统计卡片、快捷入口、运行任务、Agent 状态、活动流；对话框支持选择 Agent 或团队。
- 对话与任务：用户选择agents并编排流程以实现任务
- 团队管理：卡片展示、编辑团队、使用团队跳转任务大厅。
- 任务大厅：新建任务、选择团队/Agent、串行/并行/自由讨论/可视化流程编排、查看进度。
- 平台配置：大模型、Agent、Prompt、Skill、Tools、知识库、成本看板。
- 顶栏：General AI System 固定标题、语言切换、暗色/亮色、全屏、头像与姓名。

## 重要边界
会话任务已支持通过平台配置中的 OpenAI 兼容模型端点生成真实回复。先在“大模型配置”填写 Base URL、模型名称与 API Key，保存后点击“连接测试”；再在“智能体配置”中绑定模型，可选绑定 Prompt 和 Skill。之后在“对话与任务”创建任务并发送消息，单个或多个智能体会按串行/并行模式回复。模型调用失败时，用户消息仍会保存，可点击“重试上一条”。

会话及任务启动支持 SSE 流式显示模型回复；连接测试仍为普通请求，后台队列尚未接入。“自由讨论”按串行执行。文本类附件（txt、md、csv、json）的内容可加入模型上下文，其他附件目前仅存储与下载；工具连接器仅保存选择，尚未执行。API Key 不返回前端明文，但仍存于数据库；生产环境应加密存储，并加上认证、RBAC、审计及调用限额。

成本看板从模型调用日志汇总成功调用次数和供应商返回的 Token 用量，历史上未记录的调用不会追溯补算。在大模型配置中填写每百万输入/输出 Token 单价及币种后，新调用会按供应商实际 usage 估算成本；未返回 usage 或未配置单价的调用保留记录，但不虚构 Token 或金额。连接测试也计入调用记录。

知识库支持创建与编辑、上传 TXT/MD/CSV/JSON/文本型 PDF（每份最大 12 MB）、自动切分、关键词检索和删除文档。新建对话任务时可选择最多 5 个已启用知识库，模型调用前会把与本轮问题相关的片段加入上下文。扫描版 PDF 目前需要先完成 OCR；当前检索为关键词匹配，不包含参考项目的向量检索、发布版本和权限隔离。

新建对话与任务的协作模式包含“流程图编排”：选择多个智能体或团队后，可拖动节点调整执行顺序。流程保存到任务 workflow.nodes，串行执行器与流式执行器都按该顺序逐个调用模型，前一个智能体的回复会传给下一个智能体。当前流程为线性顺序，不支持条件分支或并行分叉。
