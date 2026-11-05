"""Initial durable research schema."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.String(36),primary_key=True),sa.Column('email',sa.String(254),nullable=False),
        sa.Column('name',sa.String(100),nullable=False),sa.Column('password_hash',sa.String(256),nullable=False),
        sa.Column('role',sa.String(20),nullable=False),sa.Column('active',sa.Boolean,nullable=False),
        sa.Column('settings',sa.JSON,nullable=False),sa.Column('created_at',sa.Float,nullable=False))
    op.create_index('ix_users_email','users',['email'],unique=True)
    op.create_table('sessions',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False),sa.Column('expires_at',sa.Float,nullable=False),sa.Column('revoked',sa.Boolean,nullable=False))
    op.create_index('ix_sessions_user_id','sessions',['user_id'])
    op.create_index('ix_sessions_token_hash','sessions',['token_hash'],unique=True)
    op.create_table('resources',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(30),nullable=False),sa.Column('name',sa.String(160),nullable=False),
        sa.Column('source_id',sa.String(36),sa.ForeignKey('resources.id'),nullable=True),sa.Column('data',sa.JSON,nullable=False),sa.Column('created_at',sa.Float,nullable=False))
    for col in ['owner_id','kind','source_id','created_at']:op.create_index('ix_resources_'+col,'resources',[col])
    op.create_table('jobs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(30),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('config',sa.JSON,nullable=False),sa.Column('details',sa.JSON,nullable=False),
        sa.Column('completed',sa.Integer,nullable=False),sa.Column('total',sa.Integer,nullable=False),sa.Column('heartbeat',sa.Float,nullable=False),sa.Column('cancel_requested',sa.Boolean,nullable=False),
        sa.Column('result_id',sa.String(36),sa.ForeignKey('resources.id')),sa.Column('error',sa.String(1000)),sa.Column('created_at',sa.Float,nullable=False))
    for col in ['owner_id','status','created_at']:op.create_index('ix_jobs_'+col,'jobs',[col])
    op.create_table('notifications',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('message',sa.String(500),nullable=False),sa.Column('job_id',sa.String(36),sa.ForeignKey('jobs.id')),sa.Column('read',sa.Boolean,nullable=False),sa.Column('created_at',sa.Float,nullable=False))
    op.create_index('ix_notifications_owner_id','notifications',['owner_id'])
    op.create_table('audit_events',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id')),
        sa.Column('action',sa.String(100),nullable=False),sa.Column('target',sa.String(200),nullable=False),sa.Column('created_at',sa.Float,nullable=False))
    for col in ['owner_id','action','created_at']:op.create_index('ix_audit_events_'+col,'audit_events',[col])
    op.create_table('worker_leases',sa.Column('id',sa.String(100),primary_key=True),sa.Column('heartbeat',sa.Float,nullable=False))

def downgrade():
    for table in ['worker_leases','audit_events','notifications','jobs','resources','sessions','users']:op.drop_table(table)
