"""Exercise the actual hosted launcher with isolated SQLite and local HTTP."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import uuid

class HostedServiceTests(unittest.TestCase):
    def test_launcher_migrates_starts_api_and_processes_a_job(self):
        with tempfile.TemporaryDirectory(prefix='pricemesh-hosted-') as folder:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env={**os.environ,'APP_ENV':'production','DATA_DIR':folder,'PORT':str(port),
                 'DATABASE_URL':'sqlite:///'+(Path(folder)/'hosted.db').as_posix(),
                 'JWT_SECRET':'test-only-hosted-secret-longer-than-32-characters',
                 'CORS_ORIGINS':'https://pricemesh-dynamic-pricing.vercel.app'}
            flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
            with (Path(folder)/'service.log').open('w') as log:
                process=subprocess.Popen([sys.executable,'-m','backend.app.serve'],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
                token=''
                def request(path,body=None):
                    headers={'Content-Type':'application/json','Origin':env['CORS_ORIGINS']}
                    if token:headers['Authorization']='Bearer '+token
                    req=urllib.request.Request(f'http://127.0.0.1:{port}/api/v1'+path,headers=headers,
                        data=json.dumps(body).encode() if body is not None else None)
                    with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
                try:
                    deadline=time.monotonic()+60
                    while time.monotonic()<deadline:
                        if process.poll() is not None:self.fail('Hosted launcher exited before readiness')
                        try:
                            if request('/health/ready')['status']=='ready':break
                        except (OSError,ValueError):time.sleep(.2)
                    else:self.fail('Hosted launcher did not become ready')
                    session=request('/auth/register',{'email':f'{uuid.uuid4()}@test.example','password':'hosted-test-password'})
                    token=session['access_token']
                    product=dict(sku='SYNTHETIC',name='Artificial product',cost=10,reference_price=20,min_price=12,max_price=30,stock=30)
                    catalog=request('/catalogs',{'name':'Hosted test catalog','products':[product]})
                    scenario=request('/scenarios',{'name':'Hosted test scenario','catalog_id':catalog['id'],'horizon':2})
                    job=request('/datasets/generate',{'scenario_id':scenario['id'],'episodes':1})
                    while time.monotonic()<deadline:
                        state=request('/jobs/'+job['id'])
                        if state['status'] in ('completed','failed'):break
                        time.sleep(.25)
                    self.assertEqual(state['status'],'completed',state)
                    self.assertEqual(request('/resources/'+state['result_id'])['data']['row_count'],2)
                    self.assertEqual(request('/system/status')['worker'],'online')
                finally:
                    if process.poll() is None:
                        if os.name=='nt':process.send_signal(signal.CTRL_BREAK_EVENT)
                        else:process.terminate()
                    try:process.wait(timeout=25)
                    except subprocess.TimeoutExpired:process.kill();process.wait();self.fail('Hosted launcher did not shut down')
