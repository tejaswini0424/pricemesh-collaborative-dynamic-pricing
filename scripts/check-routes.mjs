import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../frontend/src/pages.ts',import.meta.url),'utf8');
const routes=[...source.matchAll(/^\['(\/[^']*)'/gm)].map(m=>m[1]);
assert.equal(routes.length,32,'Expected all 32 approved routes');
assert.equal(new Set(routes).size,32,'Routes must be unique');
assert.ok(routes.includes('/dashboard'));
assert.ok(routes.includes('/system'));
console.log('Route manifest verified: 32 unique routes.');
