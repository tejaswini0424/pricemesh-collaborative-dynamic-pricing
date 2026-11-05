import os
import time
import uuid
from pathlib import Path
from sqlalchemy import create_engine, String, Float, Integer, Boolean, JSON, ForeignKey, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATA_DIR=Path(os.getenv('DATA_DIR','artifacts')).resolve()
DATA_DIR.mkdir(parents=True,exist_ok=True)
DATABASE_URL=os.getenv('DATABASE_URL',f'sqlite:///{(DATA_DIR/"pricemesh.db").as_posix()}')
engine=create_engine(DATABASE_URL,connect_args={'check_same_thread':False,'timeout':30} if DATABASE_URL.startswith('sqlite') else {},pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine,'connect')
    def sqlite_options(connection,_):
        cursor=connection.cursor();cursor.execute('PRAGMA foreign_keys=ON');cursor.execute('PRAGMA journal_mode=WAL');cursor.close()
SessionLocal=sessionmaker(engine,expire_on_commit=False)
def uid(): return str(uuid.uuid4())
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(100))
    password_hash:Mapped[str]=mapped_column(String(256))
    role:Mapped[str]=mapped_column(String(20),default='researcher')
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    settings:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[float]=mapped_column(Float,default=time.time)
class LoginSession(Base):
    __tablename__='sessions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    expires_at:Mapped[float]=mapped_column(Float)
    revoked:Mapped[bool]=mapped_column(Boolean,default=False)
class Resource(Base):
    __tablename__='resources'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    kind:Mapped[str]=mapped_column(String(30),index=True)
    name:Mapped[str]=mapped_column(String(160))
    source_id:Mapped[str|None]=mapped_column(ForeignKey('resources.id'),nullable=True,index=True)
    data:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[float]=mapped_column(Float,default=time.time,index=True)
class Job(Base):
    __tablename__='jobs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    kind:Mapped[str]=mapped_column(String(30))
    status:Mapped[str]=mapped_column(String(20),default='queued',index=True)
    config:Mapped[dict]=mapped_column(JSON)
    details:Mapped[dict]=mapped_column(JSON,default=dict)
    control:Mapped[str]=mapped_column(String(20),default='running')
    step_requests:Mapped[int]=mapped_column(Integer,default=0)
    completed:Mapped[int]=mapped_column(Integer,default=0)
    total:Mapped[int]=mapped_column(Integer,default=1)
    heartbeat:Mapped[float]=mapped_column(Float,default=time.time)
    cancel_requested:Mapped[bool]=mapped_column(Boolean,default=False)
    result_id:Mapped[str|None]=mapped_column(ForeignKey('resources.id'),nullable=True)
    error:Mapped[str|None]=mapped_column(String(1000),nullable=True)
    created_at:Mapped[float]=mapped_column(Float,default=time.time,index=True)
class Notice(Base):
    __tablename__='notifications'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    message:Mapped[str]=mapped_column(String(500))
    job_id:Mapped[str|None]=mapped_column(ForeignKey('jobs.id'),nullable=True)
    read:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[float]=mapped_column(Float,default=time.time)
class Audit(Base):
    __tablename__='audit_events'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True,index=True)
    action:Mapped[str]=mapped_column(String(100),index=True)
    target:Mapped[str]=mapped_column(String(200),default='')
    created_at:Mapped[float]=mapped_column(Float,default=time.time,index=True)
class Lease(Base):
    __tablename__='worker_leases'
    id:Mapped[str]=mapped_column(String(100),primary_key=True)
    heartbeat:Mapped[float]=mapped_column(Float,default=time.time)

def init_db():
    Base.metadata.create_all(engine)

def get_db():
    with SessionLocal() as db: yield db

def public_resource(r):
    return dict(id=r.id,name=r.name,kind=r.kind,source_id=r.source_id,data=r.data,created_at=r.created_at)

def public_job(j):
    return dict(id=j.id,kind=j.kind,status=j.status,completed=j.completed,total=j.total,
                progress=round(100*j.completed/max(j.total,1),1),result_id=j.result_id,error=j.error,
                created_at=j.created_at,cancel_requested=j.cancel_requested,details=j.details,control=j.control)
