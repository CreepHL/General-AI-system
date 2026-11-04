from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Query
from fastapi.responses import FileResponse,StreamingResponse
from fastapi.encoders import jsonable_encoder
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from datetime import timezone,timedelta
from sqlalchemy import desc,func
from ..database import get_db
from ..models import Agent,Team,Task,TaskMessage,TaskAttachment,ConfigItem,Activity,ModelUsage,KnowledgeDocument,KnowledgeChunk,AppArtifact
from ..schemas import AgentIn,TeamIn,TaskIn,TaskMessageIn,TaskConnectorsIn,ConfigIn,ConfigStatusIn,ModelTestIn
from ..services.chat_runtime import ChatConfigurationError,ChatProviderError,run_task_turn,stream_task_turn,test_model
from ..services.knowledge import extract_text,chunk_text,search_chunks
router=APIRouter(prefix='/api')
logger=logging.getLogger(__name__)
UPLOAD_DIR=Path(__file__).resolve().parents[2]/'uploads'
MAX_ATTACHMENT_SIZE=10*1024*1024
def dump(obj):
 d={c.name:getattr(obj,c.name) for c in obj.__table__.columns}
 if 'api_key' in d: d['api_key']='已配置' if d['api_key'] else ''
 return d
def validate_agent_bindings(body:AgentIn,db:Session):
 bindings=[(body.model_config_id,'models'),(body.prompt_config_id,'prompts')]
 bindings.extend((id,'skills') for id in body.skill_config_ids)
 for id,category in bindings:
  if id is None: continue
  item=db.get(ConfigItem,id)
  if not item or item.category!=category: raise HTTPException(422,f'Invalid {category} binding: {id}')
@router.get('/health')
def health(): return {'status':'ok','service':'General AI System API'}
@router.get('/dashboard')
def dashboard(db:Session=Depends(get_db)):
 agents=db.query(Agent).all(); teams=db.query(Team).all(); tasks=db.query(Task).all()
 return {'agent_count':len(agents),'team_count':len(teams),'task_count':len(tasks),'completed_today':sum(t.status=='已完成' for t in tasks),'running_tasks':[dump(t) for t in tasks if t.status=='进行中'],'agents':[dump(a) for a in agents],'activities':[dump(a) for a in db.query(Activity).order_by(desc(Activity.created_at)).limit(8).all()],'usage':costs(db)['summary']}
@router.get('/agents')
def list_agents(db:Session=Depends(get_db)): return [dump(x) for x in db.query(Agent).order_by(Agent.id).all()]
@router.post('/agents')
def create_agent(body:AgentIn,db:Session=Depends(get_db)):
 validate_agent_bindings(body,db)
 x=Agent(**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return dump(x)
@router.put('/agents/{id}')
def update_agent(id:int,body:AgentIn,db:Session=Depends(get_db)):
 x=db.get(Agent,id)
 if not x: raise HTTPException(404,'Agent not found')
 validate_agent_bindings(body,db)
 for k,v in body.model_dump().items(): setattr(x,k,v)
 db.commit(); db.refresh(x); return dump(x)
@router.delete('/agents/{id}')
def delete_agent(id:int,db:Session=Depends(get_db)):
 x=db.get(Agent,id)
 if not x: raise HTTPException(404,'Agent not found')
 db.delete(x); db.commit(); return {'ok':True}
@router.get('/teams')
def list_teams(db:Session=Depends(get_db)): return [dump(x) for x in db.query(Team).order_by(Team.id).all()]
@router.post('/teams')
def create_team(body:TeamIn,db:Session=Depends(get_db)):
 x=Team(**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return dump(x)
@router.put('/teams/{id}')
def update_team(id:int,body:TeamIn,db:Session=Depends(get_db)):
 x=db.get(Team,id)
 if not x: raise HTTPException(404,'Team not found')
 for k,v in body.model_dump().items(): setattr(x,k,v)
 db.commit(); db.refresh(x); return dump(x)
@router.delete('/teams/{id}')
def delete_team(id:int,db:Session=Depends(get_db)):
 x=db.get(Team,id)
 if not x: raise HTTPException(404,'Team not found')
 db.delete(x); db.commit(); return {'ok':True}
@router.get('/tasks')
def list_tasks(db:Session=Depends(get_db)): return [dump(x) for x in db.query(Task).order_by(desc(Task.created_at)).all()]
@router.get('/tasks/running-count')
def running_task_count(db:Session=Depends(get_db)):
 return {'count':db.query(Task).filter(Task.status=='进行中').count()}
@router.get('/tasks/{id}/app')
def get_task_app(id:int,db:Session=Depends(get_db)):
 if not db.get(Task,id): raise HTTPException(404,'Task not found')
 artifact=db.query(AppArtifact).filter(AppArtifact.task_id==id).order_by(desc(AppArtifact.version)).first()
 return dump(artifact) if artifact else None
@router.get('/tasks/{id}/app/versions')
def get_task_app_versions(id:int,db:Session=Depends(get_db)):
 if not db.get(Task,id): raise HTTPException(404,'Task not found')
 return [{'id':item.id,'version':item.version,'title':item.title,'created_at':item.created_at}
         for item in db.query(AppArtifact).filter(AppArtifact.task_id==id).order_by(desc(AppArtifact.version)).all()]
@router.get('/tasks/{id}/app/versions/{version}')
def get_task_app_version(id:int,version:int,db:Session=Depends(get_db)):
 if not db.get(Task,id): raise HTTPException(404,'Task not found')
 artifact=db.query(AppArtifact).filter(AppArtifact.task_id==id,AppArtifact.version==version).first()
 if not artifact: raise HTTPException(404,'应用版本不存在')
 return dump(artifact)
@router.post('/tasks/{id}/app/versions/{version}/restore')
def restore_task_app_version(id:int,version:int,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task or not (task.workflow or {}).get('app_mode'): raise HTTPException(404,'应用任务不存在')
 source=db.query(AppArtifact).filter(AppArtifact.task_id==id,AppArtifact.version==version).first()
 if not source: raise HTTPException(404,'应用版本不存在')
 newest=db.query(func.max(AppArtifact.version)).filter(AppArtifact.task_id==id).scalar() or 0
 artifact=AppArtifact(task_id=id,version=newest+1,title=source.title,html=source.html,css=source.css,javascript=source.javascript)
 db.add(artifact); task.status='可预览'; task.progress=100; task.result=''; db.commit(); db.refresh(artifact)
 return dump(artifact)
@router.post('/tasks')
def create_task(body:TaskIn,db:Session=Depends(get_db)):
 knowledge_ids=(body.workflow or {}).get('knowledge_ids') or []
 if not isinstance(knowledge_ids,list) or len(knowledge_ids)>5 or any(not isinstance(value,int) or isinstance(value,bool) for value in knowledge_ids): raise HTTPException(422,'知识库选择无效')
 if knowledge_ids:
  available=db.query(ConfigItem).filter(ConfigItem.category=='knowledge',ConfigItem.status=='已启用',ConfigItem.id.in_(knowledge_ids)).count()
  if available!=len(set(knowledge_ids)): raise HTTPException(422,'所选知识库不存在或未启用')
 if body.collaboration_mode=='流程图编排':
  nodes=(body.workflow or {}).get('nodes')
  if body.target_type=='team':
   team=db.get(Team,body.team_id or body.target_id)
   if not team: raise HTTPException(422,'所选团队不存在')
   selected_ids=team.agent_ids or []
  else:
   selected_ids=(body.workflow or {}).get('agent_ids') or []
  if not isinstance(nodes,list) or not nodes or len(nodes)>30 or not isinstance(selected_ids,list): raise HTTPException(422,'流程图节点无效')
  ordered=[node.get('agent_id') if isinstance(node,dict) else None for node in nodes]
  if any(not isinstance(agent_id,int) or isinstance(agent_id,bool) for agent_id in ordered): raise HTTPException(422,'流程图包含无效的智能体编号')
  if len(ordered)!=len(selected_ids) or len(set(ordered))!=len(ordered) or set(ordered)!=set(selected_ids): raise HTTPException(422,'流程图节点必须与所选智能体一致')
  if any(not (agent:=db.get(Agent,agent_id)) or not agent.enabled for agent_id in ordered): raise HTTPException(422,'流程图包含无效或未启用的智能体')
 x=Task(**body.model_dump()); db.add(x); db.flush()
 if x.description.strip(): db.add(TaskMessage(task_id=x.id,role='user',content=x.description.strip()))
 db.add(Activity(title=f'新任务「{x.title}」已创建',detail=f'{x.target_name} · {x.collaboration_mode}',kind='task')); db.commit(); db.refresh(x); return dump(x)
@router.post('/tasks/{id}/start')
def start_task(id:int,db:Session=Depends(get_db)):
 x=db.get(Task,id)
 if not x: raise HTTPException(404,'Task not found')
 if x.status in {'进行中','已完成'}: raise HTTPException(409,'任务已经启动')
 latest=db.query(TaskMessage).filter(TaskMessage.task_id==id,TaskMessage.role=='user').order_by(desc(TaskMessage.id)).first()
 if not latest: raise HTTPException(422,'请先发送任务描述或消息')
 try: run_task_turn(db,x,latest)
 except ChatConfigurationError as exc: raise HTTPException(422,str(exc)) from exc
 except ChatProviderError as exc: raise HTTPException(502,str(exc)) from exc
 db.refresh(x); return dump(x)
@router.get('/tasks/{id}/messages')
def list_task_messages(id:int,db:Session=Depends(get_db)):
 if not db.get(Task,id): raise HTTPException(404,'Task not found')
 return [dump(x) for x in db.query(TaskMessage).filter(TaskMessage.task_id==id).order_by(TaskMessage.id).all()]
@router.post('/tasks/{id}/messages')
def create_task_message(id:int,body:TaskMessageIn,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 content=body.content.strip()
 if not content: raise HTTPException(422,'Message cannot be empty')
 latest=db.query(TaskMessage).filter(TaskMessage.task_id==id).order_by(desc(TaskMessage.id)).first()
 if latest and latest.role=='user': raise HTTPException(409,'上一条消息尚未收到回复，请先重试')
 x=TaskMessage(task_id=id,role='user',content=content); db.add(x); db.commit(); db.refresh(x)
 try: replies=run_task_turn(db,task,x)
 except ChatConfigurationError as exc: raise HTTPException(422,str(exc)) from exc
 except ChatProviderError as exc: raise HTTPException(502,str(exc)) from exc
 return {'user_message':dump(x),'replies':[dump(reply) for reply in replies]}
def task_stream(db:Session,task:Task,latest:TaskMessage|None,user_message:dict|None=None,prompt_override:str|None=None):
 session_factory=sessionmaker(bind=db.get_bind())
 task_id,latest_id=task.id,latest.id if latest else None
 def events():
  if user_message: yield 'data: '+json.dumps(jsonable_encoder({'type':'user_message','message':user_message}),ensure_ascii=False)+'\n\n'
  with session_factory() as stream_db:
   stream_task=None
   try:
    stream_task=stream_db.get(Task,task_id)
    stream_latest=stream_db.get(TaskMessage,latest_id) if latest_id else None
    if prompt_override is not None:
     stream_latest=SimpleNamespace(content=prompt_override)
    for event in stream_task_turn(stream_db,stream_task,stream_latest):
     yield 'data: '+json.dumps(jsonable_encoder(event),ensure_ascii=False)+'\n\n'
   except (ChatConfigurationError,ChatProviderError) as exc:
    if stream_task and (stream_task.workflow or {}).get('app_mode') and stream_task.status!='生成失败':
     stream_task.status='生成失败'; stream_task.progress=0; stream_task.result=str(exc)[:500]; stream_db.commit()
    yield 'data: '+json.dumps({'type':'error','detail':str(exc)},ensure_ascii=False)+'\n\n'
   except Exception:
    logger.exception('Task stream failed for task %s',task_id)
    stream_db.rollback()
    try:
     failed_task=stream_db.get(Task,task_id)
     if failed_task and (failed_task.workflow or {}).get('app_mode'):
      failed_task.status='生成失败'; failed_task.progress=0; failed_task.result='应用生成遇到内部错误，请稍后重试'; stream_db.commit()
    except Exception:
     logger.exception('Unable to persist failed app status for task %s',task_id)
    yield 'data: '+json.dumps({'type':'error','detail':'应用生成遇到内部错误，请稍后重试'},ensure_ascii=False)+'\n\n'
 return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
@router.post('/tasks/{id}/messages/stream')
def create_task_message_stream(id:int,body:TaskMessageIn,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 content=body.content.strip()
 if not content: raise HTTPException(422,'Message cannot be empty')
 latest=db.query(TaskMessage).filter(TaskMessage.task_id==id).order_by(desc(TaskMessage.id)).first()
 if latest and latest.role=='user': raise HTTPException(409,'上一条消息尚未收到回复，请先重试')
 x=TaskMessage(task_id=id,role='user',content=content); db.add(x); db.commit(); db.refresh(x)
 return task_stream(db,task,x,dump(x))
@router.post('/tasks/{id}/retry/stream')
def retry_task_message_stream(id:int,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 latest=db.query(TaskMessage).filter(TaskMessage.task_id==id).order_by(desc(TaskMessage.id)).first()
 if not latest or latest.role!='user': raise HTTPException(422,'没有可重试的用户消息')
 return task_stream(db,task,latest)
@router.post('/tasks/{id}/app/rebuild/stream')
def rebuild_task_app_stream(id:int,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 if db.query(AppArtifact).filter(AppArtifact.task_id==id).first():
  raise HTTPException(409,'已有可预览版本，请在对话中发送修改要求')
 requests=db.query(TaskMessage).filter(TaskMessage.task_id==id,TaskMessage.role=='user').order_by(TaskMessage.id).all()
 prompt='\n\n'.join(message.content.strip() for message in requests if message.content.strip()) or (task.description or '').strip()
 if not prompt: raise HTTPException(422,'没有可重新执行的原始需求')
 if len(prompt)>20000: raise HTTPException(422,'历史需求过长，请在新任务中精简后生成')
 task.workflow={**(task.workflow or {}),'app_mode':True}
 db.commit()
 return task_stream(db,task,requests[-1] if requests else None,prompt_override=prompt)
@router.post('/tasks/{id}/start/stream')
def start_task_stream(id:int,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 if task.status in {'进行中','已完成'}: raise HTTPException(409,'任务已经启动')
 latest=db.query(TaskMessage).filter(TaskMessage.task_id==id,TaskMessage.role=='user').order_by(desc(TaskMessage.id)).first()
 if not latest: raise HTTPException(422,'请先发送任务描述或消息')
 return task_stream(db,task,latest)
@router.post('/tasks/{id}/retry')
def retry_task_message(id:int,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 latest=db.query(TaskMessage).filter(TaskMessage.task_id==id).order_by(desc(TaskMessage.id)).first()
 if not latest or latest.role!='user': raise HTTPException(422,'没有可重试的用户消息')
 try: replies=run_task_turn(db,task,latest)
 except ChatConfigurationError as exc: raise HTTPException(422,str(exc)) from exc
 except ChatProviderError as exc: raise HTTPException(502,str(exc)) from exc
 return {'replies':[dump(reply) for reply in replies]}
@router.put('/tasks/{id}/connectors')
def update_task_connectors(id:int,body:TaskConnectorsIn,db:Session=Depends(get_db)):
 task=db.get(Task,id)
 if not task: raise HTTPException(404,'Task not found')
 codes=list(dict.fromkeys(body.codes))
 available={x.code for x in db.query(ConfigItem).filter(ConfigItem.category=='tools',ConfigItem.status=='已启用').all()}
 if len(codes)>20 or any(code not in available for code in codes): raise HTTPException(422,'Invalid connector selection')
 task.workflow={**(task.workflow or {}),'connector_codes':codes}
 db.commit(); db.refresh(task); return dump(task)
@router.get('/tasks/{id}/attachments')
def list_task_attachments(id:int,db:Session=Depends(get_db)):
 if not db.get(Task,id): raise HTTPException(404,'Task not found')
 return [dump(x) for x in db.query(TaskAttachment).filter(TaskAttachment.task_id==id).order_by(TaskAttachment.id).all()]
@router.post('/tasks/{id}/attachments')
async def upload_task_attachment(id:int,file:UploadFile=File(...),db:Session=Depends(get_db)):
 if not db.get(Task,id): raise HTTPException(404,'Task not found')
 filename=Path(file.filename or '').name.strip()
 if not filename or len(filename)>255: raise HTTPException(422,'Invalid filename')
 data=await file.read(MAX_ATTACHMENT_SIZE+1)
 if len(data)>MAX_ATTACHMENT_SIZE: raise HTTPException(413,'Attachment exceeds 10 MB')
 UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
 storage_name=uuid4().hex
 destination=UPLOAD_DIR/storage_name
 destination.write_bytes(data)
 try:
  item=TaskAttachment(task_id=id,filename=filename,storage_name=storage_name,content_type=file.content_type or 'application/octet-stream',size=len(data))
  db.add(item); db.commit(); db.refresh(item); return dump(item)
 except Exception:
  destination.unlink(missing_ok=True)
  raise
@router.get('/tasks/{id}/attachments/{attachment_id}')
def download_task_attachment(id:int,attachment_id:int,db:Session=Depends(get_db)):
 item=db.get(TaskAttachment,attachment_id)
 if not item or item.task_id!=id: raise HTTPException(404,'Attachment not found')
 path=UPLOAD_DIR/item.storage_name
 if not path.is_file(): raise HTTPException(404,'Attachment file not found')
 return FileResponse(path,media_type='application/octet-stream',filename=item.filename)
@router.get('/config/{category}')
def list_config(category:str,db:Session=Depends(get_db)):
 items=[dump(x) for x in db.query(ConfigItem).filter(ConfigItem.category==category).order_by(ConfigItem.id).all()]
 if category=='knowledge':
  counts=dict(db.query(KnowledgeDocument.knowledge_id,func.count(KnowledgeDocument.id)).group_by(KnowledgeDocument.knowledge_id).all())
  for item in items: item['document_count']=counts.get(item['id'],0)
 return items
def knowledge_base(id:int,db:Session):
 item=db.get(ConfigItem,id)
 if not item or item.category!='knowledge': raise HTTPException(404,'知识库不存在')
 return item
@router.get('/knowledge/search')
def search_knowledge(q:str=Query(min_length=1,max_length=500),knowledge_id:int|None=None,limit:int=8,db:Session=Depends(get_db)):
 if not q.strip(): raise HTTPException(422,'请输入检索内容')
 if knowledge_id is not None: knowledge_base(knowledge_id,db)
 hits=search_chunks(db,q.strip(),knowledge_id,max(1,min(limit,20)))
 documents={doc.id:doc.filename for doc in db.query(KnowledgeDocument).filter(KnowledgeDocument.id.in_([hit['document_id'] for hit in hits])).all()}
 for hit in hits: hit['filename']=documents.get(hit['document_id'],'')
 return {'query':q,'count':len(hits),'items':hits}
@router.get('/knowledge/{id}/documents')
def knowledge_documents(id:int,db:Session=Depends(get_db)):
 knowledge_base(id,db)
 return [dump(doc) for doc in db.query(KnowledgeDocument).filter(KnowledgeDocument.knowledge_id==id).order_by(desc(KnowledgeDocument.created_at)).all()]
@router.post('/knowledge/{id}/documents')
async def upload_knowledge_document(id:int,file:UploadFile=File(...),db:Session=Depends(get_db)):
 knowledge_base(id,db)
 filename=Path(file.filename or '').name.strip()
 if not filename or len(filename)>255: raise HTTPException(422,'文件名无效')
 data=await file.read(12*1024*1024+1)
 if len(data)>12*1024*1024: raise HTTPException(413,'文件不可超过 12 MB')
 try: chunks=chunk_text(extract_text(filename,data))
 except ValueError as exc: raise HTTPException(422,str(exc)) from exc
 document=KnowledgeDocument(knowledge_id=id,filename=filename,content_type=file.content_type or 'application/octet-stream',size=len(data),chunk_count=len(chunks))
 db.add(document); db.flush()
 db.add_all(KnowledgeChunk(document_id=document.id,knowledge_id=id,ordinal=index,content=content) for index,content in enumerate(chunks))
 db.commit(); db.refresh(document)
 return dump(document)
@router.delete('/knowledge/{id}/documents/{document_id}')
def delete_knowledge_document(id:int,document_id:int,db:Session=Depends(get_db)):
 knowledge_base(id,db)
 document=db.get(KnowledgeDocument,document_id)
 if not document or document.knowledge_id!=id: raise HTTPException(404,'文档不存在')
 db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id==document_id).delete()
 db.delete(document); db.commit()
 return {'ok':True}
@router.post('/config/models/{id}/test')
def test_model_connection(id:int,body:ModelTestIn,db:Session=Depends(get_db)):
 model=db.get(ConfigItem,id)
 if not model or model.category!='models': raise HTTPException(404,'Model not found')
 try: return test_model(model,body.api_key)
 except ChatConfigurationError as exc: raise HTTPException(422,str(exc)) from exc
 except ChatProviderError as exc: raise HTTPException(502,str(exc)) from exc
@router.post('/config')
def create_config(body:ConfigIn,db:Session=Depends(get_db)):
 x=ConfigItem(**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return dump(x)
@router.patch('/config/{id}/status')
def update_config_status(id:int,body:ConfigStatusIn,db:Session=Depends(get_db)):
 x=db.get(ConfigItem,id)
 if not x: raise HTTPException(404,'Config not found')
 x.status=body.status
 db.commit(); db.refresh(x); return dump(x)
@router.put('/config/{id}')
def update_config(id:int,body:ConfigIn,db:Session=Depends(get_db)):
 x=db.get(ConfigItem,id)
 if not x: raise HTTPException(404,'Config not found')
 values=body.model_dump()
 if not values.get('api_key'): values['api_key']=x.api_key
 for k,v in values.items(): setattr(x,k,v)
 db.commit(); db.refresh(x); return dump(x)
@router.delete('/config/{id}')
def delete_config(id:int,db:Session=Depends(get_db)):
 x=db.get(ConfigItem,id)
 if not x: raise HTTPException(404,'Config not found')
 if x.category=='knowledge':
  document_ids=[row[0] for row in db.query(KnowledgeDocument.id).filter(KnowledgeDocument.knowledge_id==id).all()]
  if document_ids: db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id.in_(document_ids)).delete(synchronize_session=False)
  db.query(KnowledgeDocument).filter(KnowledgeDocument.knowledge_id==id).delete(synchronize_session=False)
 db.delete(x); db.commit(); return {'ok':True}
@router.get('/costs')
def costs(db:Session=Depends(get_db)):
 rows=db.query(ModelUsage).order_by(ModelUsage.created_at).all()
 summary={'calls':len(rows),'tokens':0,'input_tokens':0,'output_tokens':0,'unreported_usage_calls':0,'unpriced_calls':0,'estimated_cost_by_currency':{}}
 days={}
 for row in rows:
  day=row.created_at.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
  item=days.setdefault(day,{'date':day,'calls':0,'tokens':0,'input_tokens':0,'output_tokens':0,'cost_by_currency':{}})
  item['calls']+=1
  for field in ('tokens','input_tokens','output_tokens'):
   value=row.total_tokens if field=='tokens' else getattr(row,field)
   summary[field]+=value or 0
   item[field]+=value or 0
  if row.total_tokens is None: summary['unreported_usage_calls']+=1
  if row.estimated_cost is None: summary['unpriced_calls']+=1
  else:
   currency=row.currency
   summary['estimated_cost_by_currency'][currency]=summary['estimated_cost_by_currency'].get(currency,0)+row.estimated_cost
   item['cost_by_currency'][currency]=item['cost_by_currency'].get(currency,0)+row.estimated_cost
 return {'summary':summary,'by_day':list(days.values())}
