from alembic import context
from backend.app.database import Base,engine

def run(connection):
    context.configure(connection=connection,target_metadata=Base.metadata,compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

provided=context.config.attributes.get('connection')
if provided is not None:run(provided)
else:
    with engine.connect() as connection:run(connection)
