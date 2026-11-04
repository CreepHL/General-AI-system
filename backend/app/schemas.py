from pydantic import BaseModel,Field
from typing import Any,Literal
class AgentIn(BaseModel):
 name:str; role:str='通用助手'; description:str=''; model_name:str='DeepSeek-V3'; temperature:float=.3; memory_type:str='短期记忆'; prompt:str=''; tools:list[str]=Field(default_factory=list); status:str='在线'; enabled:bool=True
 model_config_id:int|None=None; prompt_config_id:int|None=None; skill_config_ids:list[int]=Field(default_factory=list)
class TeamIn(BaseModel):
 name:str; description:str=''; mode:str='串行'; is_template:bool=False; agent_ids:list[int]=Field(default_factory=list)
class TaskIn(BaseModel):
 title:str; description:str=''; target_type:str='team'; target_id:int|None=None; target_name:str=''; team_id:int|None=None; collaboration_mode:str='串行'; workflow:dict[str,Any]=Field(default_factory=dict)
class TaskMessageIn(BaseModel):
 content:str=Field(min_length=1,max_length=10000)
class ModelTestIn(BaseModel):
 api_key:str=''
class TaskConnectorsIn(BaseModel):
 codes:list[str]=Field(default_factory=list)
class ConfigIn(BaseModel):
 category:str; name:str; code:str=''; provider:str=''; model_name:str=''; base_url:str=''; api_key:str=''; description:str=''; content:str=''; status:str='已启用'; is_default:bool=False; extra:dict[str,Any]=Field(default_factory=dict)
class ConfigStatusIn(BaseModel):
 status:Literal['已启用','已停用']
