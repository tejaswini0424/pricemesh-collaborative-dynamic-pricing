"""Single-instance hosted service: migrations, API and supervised queue worker.

API and worker share DATA_DIR. Use this entrypoint on a host whose persistent
disk cannot be shared across separate services. This is not a scale-out setup.
"""
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[2]
log=logging.getLogger('pricemesh.serve')

def main():
    logging.basicConfig(level=logging.INFO)
    port=int(os.getenv('PORT','8000'))
    if not 1<=port<=65535: raise ValueError('PORT must be between 1 and 65535')
    if os.getenv('APP_ENV')=='production' and len(os.getenv('JWT_SECRET',''))<32:
        raise RuntimeError('Set JWT_SECRET to at least 32 random characters before starting production')
    # Migration happens at runtime: Render disks are unavailable during builds.
    subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],cwd=ROOT,check=True)
    stop=threading.Event()
    def shutdown(*_): stop.set()
    signal.signal(signal.SIGINT,shutdown)
    signal.signal(signal.SIGTERM,shutdown)
    if hasattr(signal,'SIGBREAK'): signal.signal(signal.SIGBREAK,shutdown)
    processes=[]
    result=0
    try:
        commands=[['-m','backend.app.worker'],['-m','uvicorn','backend.app.main:app','--host','0.0.0.0','--port',str(port),'--workers','1','--proxy-headers','--forwarded-allow-ips','127.0.0.1']]
        for args in commands:
            processes.append(subprocess.Popen([sys.executable,*args],cwd=ROOT,env=os.environ.copy()))
        log.info('API and worker started on port %s',port)
        while not stop.wait(.25):
            if any(p.poll() is not None for p in processes):
                log.error('A supervised process exited; stopping the service for host restart')
                result=1
                break
    finally:
        # Stop API first so no further jobs are submitted during shutdown.
        for process in reversed(processes):
            if process.poll() is None: process.terminate()
        for process in processes:
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
    return result

if __name__=='__main__':sys.exit(main())
