import {test} from 'node:test';
import assert from 'node:assert/strict';
import {backendOrigin,withBackend} from './connect-backend.mjs';
test('requires a secure public origin without embedded secrets or paths',()=>{
 assert.equal(backendOrigin('https://pricemesh.example/'),'https://pricemesh.example');
 for(const value of ['http://api.example','https://user:password@api.example','https://api.example/api','https://api.example/?token=secret','https://localhost']){
  assert.throws(()=>backendOrigin(value));
 }
});
test('places API proxy before SPA fallback and replaces an older backend',()=>{
 const config={framework:'vite',rewrites:[{source:'/api/:path*',destination:'https://old.example/api/:path*'},{source:'/((?!api(?:/|$)).*)',destination:'/index.html'}]};
 const result=withBackend(config,'https://new.example');
 assert.equal(result.framework,'vite');
 assert.equal(result.rewrites[0].destination,'https://new.example/api/:path*');
 assert.equal(result.rewrites.filter(r=>r.source==='/api/:path*').length,1);
 assert.equal(result.rewrites.at(-1).destination,'/index.html');
 assert.deepEqual(withBackend(result,'https://new.example'),result);
});
