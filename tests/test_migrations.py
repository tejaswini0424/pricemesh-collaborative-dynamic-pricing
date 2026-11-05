import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from sqlalchemy import create_engine,inspect,text

class MigrationTests(unittest.TestCase):
    def test_fresh_database_upgrade_and_restart(self):
        with tempfile.TemporaryDirectory(prefix='pricemesh-migration-') as folder:
            url='sqlite:///'+(Path(folder)/'migration.db').as_posix()
            env={**os.environ,'DATABASE_URL':url,'DATA_DIR':folder}
            for _ in range(2):
                result=subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            engine=create_engine(url)
            try:
                self.assertIn('resources',inspect(engine).get_table_names())
                self.assertIn('control',[c['name'] for c in inspect(engine).get_columns('jobs')])
                with engine.connect() as db:self.assertEqual(db.scalar(text('select version_num from alembic_version')),'0002')
            finally:engine.dispose()
