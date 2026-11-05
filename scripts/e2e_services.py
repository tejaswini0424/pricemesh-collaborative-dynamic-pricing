"""Start disposable local API + worker for browser tests only."""
import os
import subprocess
import sys
import uvicorn
from backend.app.database import init_db,DATA_DIR

if __name__=='__main__':
    if 'e2e-' not in str(DATA_DIR):raise RuntimeError('E2E services require an explicitly isolated test directory')
    init_db()
    worker=subprocess.Popen([sys.executable,'-m','backend.app.worker'],env=os.environ.copy())
    try:uvicorn.run('backend.app.main:app',host='127.0.0.1',port=8100,log_level='warning')
    finally:
        worker.terminate()
        try:worker.wait(timeout=10)
        except subprocess.TimeoutExpired:worker.kill();worker.wait()
