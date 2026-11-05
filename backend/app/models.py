from datetime import datetime
from sqlalchemy import String,Text,Integer,Float,Boolean,DateTime,JSON,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class Agent(Base):
 __tablename__='agents'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True); name:Mapped[str]=mapped_column(String(120)); role:Mapped[str]=mapped_column(String(80),default='通用助手'); description:Mapped[str]=mapped_column(String(500),default=''); model_name:Mapped[str]=mapped_column(String(120),default='DeepSeek-V3'); temperature:Mapped[float]=mapped_column(Float,default=.3); memory_type:Mapped[str]=mapped_column(String(40),default='短期记忆'); prompt:Mapped[str]=mapped_column(Text,default=''); tools:Mapped[list]=mapped_column(JSON,default=list); status:Mapped[str]=mapped_column(String(30),default='在线'); enabled:Mapped[bool]=mapped_column(Boolean,default=True); completed_tasks:Mapped[int]=mapped_column(Integer,default=0); success_rate:Mapped[float]=mapped_column(Float,default=.95); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
 model_config_id:Mapped[int|None]=mapped_column(Integer,nullable=True); prompt_config_id:Mapped[int|None]=mapped_column(Integer,nullable=True); skill_config_ids:Mapped[list]=mapped_column(JSON,default=list); tool_config_ids:Mapped[list]=mapped_column(JSON,default=list)
class Team(Base):
 __tablename__='teams'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True); name:Mapped[str]=mapped_column(String(120)); description:Mapped[str]=mapped_column(String(500),default=''); mode:Mapped[str]=mapped_column(String(40),default='串行'); is_template:Mapped[bool]=mapped_column(Boolean,default=False); agent_ids:Mapped[list]=mapped_column(JSON,default=list); completed_tasks:Mapped[int]=mapped_column(Integer,default=0); running_tasks:Mapped[int]=mapped_column(Integer,default=0); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Task(Base):
 __tablename__='tasks'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True); title:Mapped[str]=mapped_column(String(200)); description:Mapped[str]=mapped_column(Text,default=''); target_type:Mapped[str]=mapped_column(String(30),default='team'); target_id:Mapped[int|None]=mapped_column(Integer,nullable=True); target_name:Mapped[str]=mapped_column(String(120),default=''); team_id:Mapped[int|None]=mapped_column(Integer,nullable=True); collaboration_mode:Mapped[str]=mapped_column(String(40),default='串行'); status:Mapped[str]=mapped_column(String(30),default='待执行'); progress:Mapped[int]=mapped_column(Integer,default=0); result:Mapped[str]=mapped_column(Text,default=''); workflow:Mapped[dict]=mapped_column(JSON,default=dict); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
class TaskMessage(Base):
 __tablename__='task_messages'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True); task_id:Mapped[int]=mapped_column(Integer,index=True); role:Mapped[str]=mapped_column(String(20),default='user'); content:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
 agent_name:Mapped[str]=mapped_column(String(120),default='')
 details:Mapped[dict]=mapped_column(JSON,default=dict)
class AppArtifact(Base):
 __tablename__='app_artifacts'
 __table_args__=(UniqueConstraint('task_id','version',name='uq_app_artifact_task_version'),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
 task_id:Mapped[int]=mapped_column(Integer,index=True)
 version:Mapped[int]=mapped_column(Integer)
 title:Mapped[str]=mapped_column(String(200))
 html:Mapped[str]=mapped_column(Text)
 css:Mapped[str]=mapped_column(Text)
 javascript:Mapped[str]=mapped_column(Text)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class AppData(Base):
 __tablename__='app_data'
 __table_args__=(UniqueConstraint('task_id','key',name='uq_app_data_task_key'),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
 task_id:Mapped[int]=mapped_column(Integer,index=True)
 key:Mapped[str]=mapped_column(String(100))
 value_json:Mapped[str]=mapped_column(Text)
 updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
class TaskAttachment(Base):
 __tablename__='task_attachments'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True); task_id:Mapped[int]=mapped_column(Integer,index=True); filename:Mapped[str]=mapped_column(String(255)); storage_name:Mapped[str]=mapped_column(String(64)); content_type:Mapped[str]=mapped_column(String(160),default='application/octet-stream'); size:Mapped[int]=mapped_column(Integer); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class ConfigItem(Base):
 __tablename__='config_items'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True); category:Mapped[str]=mapped_column(String(40),index=True); name:Mapped[str]=mapped_column(String(160)); code:Mapped[str]=mapped_column(String(160),default=''); provider:Mapped[str]=mapped_column(String(100),default=''); model_name:Mapped[str]=mapped_column(String(160),default=''); base_url:Mapped[str]=mapped_column(String(500),default=''); api_key:Mapped[str]=mapped_column(String(1000),default=''); description:Mapped[str]=mapped_column(Text,default=''); content:Mapped[str]=mapped_column(Text,default=''); status:Mapped[str]=mapped_column(String(30),default='已启用'); is_default:Mapped[bool]=mapped_column(Boolean,default=False); extra:Mapped[dict]=mapped_column(JSON,default=dict); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class ModelUsage(Base):
 __tablename__='model_usage'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
 model_config_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
 model_name:Mapped[str]=mapped_column(String(160))
 provider:Mapped[str]=mapped_column(String(100),default='')
 task_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
 source:Mapped[str]=mapped_column(String(40))
 input_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
 output_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
 total_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
 estimated_cost:Mapped[float|None]=mapped_column(Float,nullable=True)
 currency:Mapped[str|None]=mapped_column(String(3),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)
class KnowledgeDocument(Base):
 __tablename__='knowledge_documents'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
 knowledge_id:Mapped[int]=mapped_column(Integer,index=True)
 filename:Mapped[str]=mapped_column(String(255))
 content_type:Mapped[str]=mapped_column(String(160),default='application/octet-stream')
 size:Mapped[int]=mapped_column(Integer)
 chunk_count:Mapped[int]=mapped_column(Integer,default=0)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class KnowledgeChunk(Base):
 __tablename__='knowledge_chunks'
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
 document_id:Mapped[int]=mapped_column(Integer,index=True)
 knowledge_id:Mapped[int]=mapped_column(Integer,index=True)
 ordinal:Mapped[int]=mapped_column(Integer)
 content:Mapped[str]=mapped_column(Text)
class Activity(Base):
 __tablename__='activities'
 id:Mapped[int]=mapped_column(Integer,primary_key=True); title:Mapped[str]=mapped_column(String(250)); detail:Mapped[str]=mapped_column(String(500),default=''); kind:Mapped[str]=mapped_column(String(40),default='task'); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
