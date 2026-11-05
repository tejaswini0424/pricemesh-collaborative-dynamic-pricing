/** Verify a hosted backend, then configure same-origin Vercel API rewrites. */
import {readFile,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

export function backendOrigin(value){
 const url=new URL(value);
 if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!=='/'){
  throw new Error('Provide a public HTTPS backend origin without credentials, paths, query parameters or fragments.');
 }
 if(['localhost','127.0.0.1','0.0.0.0','[::1]'].includes(url.hostname))throw new Error('A local address cannot serve as the production backend.');
 return url.origin;
}
export function withBackend(config,origin){
 const generatedSources=new Set(['/api/:path*','/docs','/openapi.json']);
 return {...config,rewrites:[
  {source:'/api/:path*',destination:origin+'/api/:path*'},
  {source:'/docs',destination:origin+'/docs'},
  {source:'/openapi.json',destination:origin+'/openapi.json'},
  ...(config.rewrites||[]).filter(rule=>!generatedSources.has(rule.source)),
 ]};
}
async function main(){
 const origin=backendOrigin(process.argv[2]||'');
 const response=await fetch(origin+'/api/v1/health/ready',{signal:AbortSignal.timeout(20000)});
 if(!response.ok)throw new Error('Backend readiness check failed: HTTP '+response.status);
 const health=await response.json();
 if(health.status!=='ready'||health.version!=='1.0.0')throw new Error('The endpoint is not a ready PriceMesh v1 backend.');
 const file=new URL('../frontend/vercel.json',import.meta.url);
 const config=JSON.parse(await readFile(file,'utf8'));
 await writeFile(file,JSON.stringify(withBackend(config,origin),null,2)+'\n');
 console.log('Backend verified. Vercel API rewrites now target '+origin);
 console.log('Keep VITE_API_BASE_URL unset (or /api/v1). Commit and deploy the configuration, then verify login after reload.');
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 main().catch(error=>{console.error(error.message);process.exitCode=1});
}
