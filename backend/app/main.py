import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base,engine,SessionLocal
from .seed import seed
from .routers.core import router
from sqlalchemy import inspect, text
app=FastAPI(title='General AI System API',version='0.1.0',description='Vue 3 + FastAPI multi-agent platform prototype')
origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(router)
@app.on_event('startup')
def startup():
 Base.metadata.create_all(bind=engine)
 with engine.begin() as connection:
  inspector=inspect(connection)
  upgrades={
   'agents': {'model_config_id':'INTEGER','prompt_config_id':'INTEGER','skill_config_ids':'JSON','tool_config_ids':'JSON'},
   'task_messages': {'agent_name':'VARCHAR(120)','details':'JSON'},
  }
  for table, columns in upgrades.items():
   if table not in inspector.get_table_names(): continue
   existing={column['name'] for column in inspector.get_columns(table)}
   for column, kind in columns.items():
    if column not in existing: connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {kind}'))
 db=SessionLocal()
 try: seed(db)
 finally: db.close()
@app.get('/')
def root(): return {'name':'General AI System','api_docs':'/docs','status':'ready'}
