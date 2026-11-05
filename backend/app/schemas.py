from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
class Credentials(StrictModel):
    email:str=Field(min_length=5,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password:str=Field(min_length=10,max_length=128)
    name:str=Field(default='Researcher',min_length=1,max_length=100)
    @field_validator('email')
    @classmethod
    def normalize_email(cls,v): return v.lower().strip()
class Product(StrictModel):
    sku:str=Field(min_length=1,max_length=50)
    name:str=Field(min_length=1,max_length=100)
    category:str=Field(default='General',max_length=100)
    cost:float=Field(gt=0,le=100000)
    reference_price:float=Field(gt=0,le=100000)
    min_price:float=Field(gt=0,le=100000)
    max_price:float=Field(gt=0,le=100000)
    stock:int=Field(ge=1,le=1000000)
    base_demand:float=Field(default=8,gt=0,le=10000)
    elasticity:float=Field(default=1.6,ge=.1,le=10)
    @model_validator(mode='after')
    def prices(self):
        if not self.cost<=self.min_price<=self.reference_price<=self.max_price:
            raise ValueError('Require cost ≤ minimum ≤ reference ≤ maximum price')
        return self
class Catalog(StrictModel):
    name:str=Field(min_length=1,max_length=160)
    currency:str=Field(default='INR',pattern=r'^[A-Z]{3}$')
    products:list[Product]=Field(min_length=1,max_length=20)
    @model_validator(mode='after')
    def unique_skus(self):
        if len(set(p.sku for p in self.products))!=len(self.products): raise ValueError('SKUs must be unique')
        return self
class Scenario(StrictModel):
    name:str=Field(min_length=1,max_length=160)
    catalog_id:str
    horizon:int=Field(default=30,ge=2,le=365)
    max_change:float=Field(default=.1,gt=0,le=.3)
    seasonality:float=Field(default=.2,ge=0,le=1)
    cross_elasticity:float=Field(default=.25,ge=-2,le=2)
    noise:float=Field(default=.25,ge=0,le=1)
    holding_penalty:float=Field(default=0,ge=0,le=100)
    stockout_penalty:float=Field(default=0,ge=0,le=100)
    change_penalty:float=Field(default=0,ge=0,le=100)
class Experiment(StrictModel):
    name:str=Field(min_length=1,max_length=160)
    scenario_id:str
    algorithm:Literal['ippo','mappo','shared_ppo']='mappo'
    seed:int=Field(default=42,ge=0,le=50000)
    episodes:int=Field(default=24,ge=2,le=1000)
    epochs:int=Field(default=4,ge=1,le=10)
    learning_rate:float=Field(default=.0003,ge=.000001,le=.01)
class Generate(StrictModel):
    scenario_id:str
    name:str=Field(default='Synthetic market dataset',min_length=1,max_length=160)
    episodes:int=Field(default=10,ge=1,le=100)
    seed:int=Field(default=60000,ge=50001,le=90000)
    strategy:Literal['fixed','inventory','myopic']='fixed'
class Evaluate(StrictModel):
    scenario_id:str
    policy_id:str|None=None
    name:str=Field(default='Held-out evaluation',min_length=1,max_length=160)
    episodes:int=Field(default=10,ge=2,le=100)
    seed:int=Field(default=100000,ge=100000,le=2000000000)
    strategy:Literal['fixed','inventory','myopic']='inventory'
    robustness:bool=False
class Simulate(StrictModel):
    scenario_id:str
    policy_id:str|None=None
    name:str=Field(default='Simulated marketplace',min_length=1,max_length=160)
    seed:int=Field(default=42,ge=0,le=2000000000)
    strategy:Literal['fixed','inventory','myopic']='inventory'
    step_delay:float=Field(default=.25,ge=0,le=2)
class Control(StrictModel):
    action:Literal['pause','resume','step']
class Profile(StrictModel):
    name:str=Field(min_length=1,max_length=100)
class UserUpdate(StrictModel):
    role:Literal['researcher','admin']
    active:bool
class Report(StrictModel):
    evaluation_id:str
    format:Literal['json','csv','html']='html'
class Settings(StrictModel):
    default_seed:int=Field(default=42,ge=0,le=50000)
    default_episodes:int=Field(default=24,ge=2,le=1000)
    currency:str=Field(default='INR',pattern=r'^[A-Z]{3}$')
class Compare(StrictModel):
    evaluation_a:str
    evaluation_b:str
class Drift(StrictModel):
    dataset_a:str
    dataset_b:str
class Diagnostics(StrictModel):
    policy_id:str
class Sensitivity(StrictModel):
    scenario_id:str
    policy_id:str|None=None
    name:str=Field(default='Sensitivity sweep',max_length=160)
    parameter:Literal['elasticity','demand','noise','supply']='elasticity'
    minimum:float=Field(default=.5,ge=.1,le=3)
    maximum:float=Field(default=1.5,ge=.1,le=3)
    points:int=Field(default=5,ge=2,le=10)
    episodes:int=Field(default=5,ge=2,le=30)
    seed:int=Field(default=100000,ge=100000,le=2000000000)
    @model_validator(mode='after')
    def ordered(self):
        if self.minimum>=self.maximum: raise ValueError('Minimum must be below maximum')
        return self
