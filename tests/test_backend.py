import os
import tempfile
import unittest
import json
from pathlib import Path

TEST_DIR=tempfile.TemporaryDirectory(prefix='pricemesh-tests-')
os.environ['DATA_DIR']=TEST_DIR.name
os.environ['DATABASE_URL']='sqlite:///'+(Path(TEST_DIR.name)/'test.db').as_posix()
os.environ['JWT_SECRET']='test-only-secret-key-with-more-than-32-characters'

import numpy as np
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db,SessionLocal,Job,engine
from backend.app.worker import run_once
from pricing.environment import Market,baseline_actions
from pricing.learning import train,load_policy
from pricing.evaluation import evaluate

PRODUCTS=[dict(sku='A',name='Product A',category='Test',cost=20.,reference_price=40.,min_price=25.,max_price=60.,stock=100,base_demand=8.,elasticity=1.6),
          dict(sku='B',name='Product B',category='Test',cost=15.,reference_price=30.,min_price=20.,max_price=50.,stock=80,base_demand=6.,elasticity=1.8)]
CONFIG={'products':PRODUCTS,'horizon':6,'max_change':.05,'noise':.25}

class EnvironmentTests(unittest.TestCase):
    def test_seed_and_accounting(self):
        a,b=Market(CONFIG,2),Market(CONFIG,2)
        for _ in range(6):
            a.step([4,0]);b.step([4,0])
        self.assertEqual(a.records,b.records)
        for row in a.records:
            self.assertGreaterEqual(row['inventory'],0)
            self.assertEqual(row['inventory_before']-row['units'],row['inventory'])
            self.assertAlmostEqual(row['profit'],(row['price']-row['cost'])*row['units'])
        self.assertEqual(a.metrics()['constraint_violations'],0)
        self.assertGreater(a.metrics()['interventions'],0)
        self.assertEqual(a.metrics()['units']+a.metrics()['remaining_inventory'],180)

    def test_terminal_and_invalid_actions(self):
        market=Market(CONFIG)
        with self.assertRaises(ValueError): market.step([99,0])
        for _ in range(6):market.step([2,2])
        with self.assertRaises(ValueError):market.step([2,2])

    def test_observations_do_not_expose_future_noise(self):
        a,b=Market(CONFIG,1),Market(CONFIG,5)
        np.testing.assert_array_equal(a.observe(),b.observe())
        self.assertEqual(a.observe().shape,(2,8))

    def test_paired_evaluation_deterministic(self):
        settings={'episodes':3,'seed':100000,'strategy':'fixed','robustness':True}
        a=evaluate(CONFIG,settings);b=evaluate(CONFIG,settings)
        self.assertEqual(a,b)
        self.assertEqual(len(a['summary']),7)
        for row in a['summary']:self.assertEqual(row['paired_difference'],0)

    def test_training_and_checkpoint_roundtrip(self):
        for algorithm in ['ippo','mappo','shared_ppo']:
            folder=Path(TEST_DIR.name)/algorithm
            policy,history,metadata=train(CONFIG,{'episodes':2,'seed':4,'algorithm':algorithm,'epochs':1},folder)
            loaded,_=load_policy(folder)
            np.testing.assert_array_equal(policy.actions(Market(CONFIG).observe()),loaded.actions(Market(CONFIG).observe()))
            self.assertEqual(len(history),2)
            self.assertTrue(np.isfinite(history[-1]['loss']))

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db();cls.client=TestClient(app)
    def setUp(self):
        import uuid
        email=f'{uuid.uuid4()}@test.example'
        response=self.client.post('/api/v1/auth/register',json={'email':email,'password':'test-password-123'})
        self.assertEqual(response.status_code,201,response.text)
        self.headers={'Authorization':'Bearer '+response.json()['access_token']}
    def post(self,path,data):
        response=self.client.post('/api/v1'+path,json=data,headers=self.headers)
        self.assertLess(response.status_code,300,response.text)
        return response.json()
    def get(self,path):
        response=self.client.get('/api/v1'+path,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()
    def setup_scenario(self):
        catalog=self.post('/catalogs',{'name':'Test catalog','products':PRODUCTS})
        return self.post('/scenarios',{'name':'Test scenario','catalog_id':catalog['id'],'horizon':6})

    def test_validation_and_unauthorized(self):
        response=self.client.get('/api/v1/resources')
        self.assertEqual(response.status_code,401)
        bad={**PRODUCTS[0],'min_price':1}
        response=self.client.post('/api/v1/catalogs',json={'name':'Invalid','products':[bad]},headers=self.headers)
        self.assertEqual(response.status_code,422)

    def test_ownership(self):
        scenario=self.setup_scenario()
        response=self.client.post('/api/v1/auth/register',json={'email':'other@test.example','password':'test-password-123'})
        other={'Authorization':'Bearer '+response.json()['access_token']}
        response=self.client.get('/api/v1/resources/'+scenario['id'],headers=other)
        self.assertEqual(response.status_code,404)
        response=self.client.post('/api/v1/datasets/generate',json={'scenario_id':scenario['id']},headers=other)
        self.assertEqual(response.status_code,404)

    def test_complete_workflow(self):
        scenario=self.setup_scenario()
        dataset_job=self.post('/datasets/generate',{'scenario_id':scenario['id'],'episodes':2})
        run_once()
        dataset=self.get('/jobs/'+dataset_job['id'])
        self.assertEqual(dataset['status'],'completed',dataset)
        preview=self.get('/resources/'+dataset['result_id']+'/records')
        self.assertEqual(preview['total'],24)
        experiment=self.post('/experiments',{'name':'Test MAPPO','scenario_id':scenario['id'],'episodes':2,'epochs':1})
        job=self.post('/experiments/'+experiment['id']+'/runs',{})
        run_once()
        job=self.get('/jobs/'+job['id'])
        self.assertEqual(job['status'],'completed',job)
        policy=job['result_id']
        evaluation_job=self.post('/evaluations',{'scenario_id':scenario['id'],'policy_id':policy,'episodes':2,'robustness':True})
        run_once()
        completed=self.get('/jobs/'+evaluation_job['id'])
        self.assertEqual(completed['status'],'completed',completed)
        evaluation=self.get('/resources/'+completed['result_id'])
        self.assertEqual(len(evaluation['data']['summary']),7)
        diagnostics=self.post('/analysis/diagnostics',{'policy_id':policy})
        self.assertEqual(len(diagnostics['rows']),50)
        comparison=self.post('/analysis/compare',{'evaluation_a':evaluation['id'],'evaluation_b':evaluation['id']})
        self.assertTrue(all(r['mean_difference_A_minus_B']==0 for r in comparison['paired_results']))
        drift=self.post('/analysis/drift',{'dataset_a':dataset['result_id'],'dataset_b':dataset['result_id']})
        self.assertTrue(all(r['standardized_mean_shift']==0 for r in drift['features']))
        sweep=self.post('/analysis/sensitivity',{'scenario_id':scenario['id'],'policy_id':policy,'points':2,'episodes':2})
        run_once()
        sweep=self.get('/jobs/'+sweep['id'])
        self.assertEqual(sweep['status'],'completed',sweep)
        self.assertEqual(len(self.get('/resources/'+sweep['result_id'])['data']['summary']),2)
        report=self.post('/reports',{'evaluation_id':evaluation['id'],'format':'html'})
        response=self.client.get('/api/v1/resources/'+report['id']+'/download?format=html',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertIn('PriceMesh report',response.text)
        dashboard=self.get('/dashboard')
        self.assertGreaterEqual(dashboard['counts']['policy'],1)
        simulation=self.post('/simulations',{'scenario_id':scenario['id'],'policy_id':policy})
        run_once()
        result=self.get('/jobs/'+simulation['id'])
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.get('/resources/'+result['result_id']+'/records')['total'],12)

    def test_cancel_queue(self):
        scenario=self.setup_scenario()
        job=self.post('/datasets/generate',{'scenario_id':scenario['id']})
        cancelled=self.post('/jobs/'+job['id']+'/cancel',{})
        self.assertEqual(cancelled['status'],'cancelled')

    def test_simulation_pause_step_resume_and_sse(self):
        import threading,time
        scenario=self.setup_scenario()
        job=self.post('/simulations',{'scenario_id':scenario['id'],'step_delay':.05})
        self.post('/jobs/'+job['id']+'/control',{'action':'pause'})
        worker=threading.Thread(target=run_once,daemon=True);worker.start()
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                state=self.get('/jobs/'+job['id'])
                if state['status']=='running':break
                time.sleep(.05)
            self.post('/jobs/'+job['id']+'/control',{'action':'step'})
            while time.monotonic()<deadline:
                state=self.get('/jobs/'+job['id'])
                if state['completed']==1:break
                time.sleep(.1)
            self.assertEqual(state['completed'],1,state)
            self.assertEqual(state['control'],'paused')
            self.post('/jobs/'+job['id']+'/control',{'action':'resume'})
            worker.join(8)
            state=self.get('/jobs/'+job['id'])
            self.assertEqual(state['status'],'completed',state)
            stream=self.client.get('/api/v1/jobs/'+job['id']+'/events',headers=self.headers)
            self.assertIn('"status": "completed"',stream.text)
        finally:
            self.post('/jobs/'+job['id']+'/cancel',{})
            worker.join(3)

    def test_non_admin_cannot_change_access(self):
        response=self.client.get('/api/v1/admin/users',headers=self.headers)
        self.assertEqual(response.status_code,403)

    def test_refresh_and_logout_revoke_access(self):
        refresh=self.client.post('/api/v1/auth/refresh',headers={'X-Requested-With':'PriceMesh'})
        self.assertEqual(refresh.status_code,200,refresh.text)
        old=self.client.get('/api/v1/auth/me',headers=self.headers)
        self.assertEqual(old.status_code,401)
        self.client.post('/api/v1/auth/logout',headers={'X-Requested-With':'PriceMesh'})
        headers={'Authorization':'Bearer '+refresh.json()['access_token']}
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=headers).status_code,401)

def tearDownModule():
    engine.dispose()
    TEST_DIR.cleanup()

if __name__=='__main__': unittest.main()
