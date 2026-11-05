import {defineConfig} from '@playwright/test';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'..');
const data=resolve(root,'artifacts','e2e-'+Date.now());
export default defineConfig({testDir:'./e2e',timeout:90000,workers:1,use:{baseURL:'http://127.0.0.1:5175',channel:'chrome',headless:true,trace:'retain-on-failure',viewport:{width:1440,height:1050}},webServer:[
 {command:'python -m scripts.e2e_services',cwd:root,url:'http://127.0.0.1:8100/api/v1/health/ready',timeout:120000,reuseExistingServer:false,env:{DATA_DIR:data,DATABASE_URL:'sqlite:///'+data.replaceAll('\\','/')+'/test.db',JWT_SECRET:'isolated-e2e-test-secret-not-for-production-123456',APP_ENV:'development',CORS_ORIGINS:'http://127.0.0.1:5175'}},
 {command:'npm run dev -- --port 5175 --strictPort',url:'http://127.0.0.1:5175',timeout:120000,reuseExistingServer:false,env:{PRICEMESH_API_TARGET:'http://127.0.0.1:8100'}}
]});
