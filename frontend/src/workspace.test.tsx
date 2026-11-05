// @vitest-environment jsdom
import React from 'react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {AuthProvider} from './api';
import {App} from './main';
const user={id:'test-user',name:'Test researcher',email:'researcher@test.example',role:'researcher'};
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});vi.stubGlobal('fetch',vi.fn(async(input:any,options:any)=>{
 const url=String(input);let data:any={};
 if(url.endsWith('/health/ready'))data={status:'ready'};
 else if(url.endsWith('/auth/refresh')||url.endsWith('/auth/login'))data={access_token:'test-only-token',user};
 else if(url.includes('/resources?'))data={items:[{id:'catalog-1',kind:'catalog',name:'Test catalog',data:{products:[]},created_at:0}]};
 else if(url.endsWith('/catalogs'))data={id:'new-catalog',kind:'catalog',name:JSON.parse(options.body).name};
 return {ok:true,json:async()=>data};
}));});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it('submits a real catalog API request from the authenticated form',async()=>{
 render(<MemoryRouter initialEntries={['/catalog']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
 await screen.findByRole('button',{name:'Save catalog'});
 fireEvent.change(screen.getByLabelText('Catalog name'),{target:{value:'My verified catalog'}});
 fireEvent.click(screen.getByRole('button',{name:'Save catalog'}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/catalogs'),expect.objectContaining({method:'POST',body:expect.stringContaining('My verified catalog')})));
});
it('provides bounded training inputs and real scenario selection',async()=>{
 render(<MemoryRouter initialEntries={['/training']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
 expect(await screen.findByRole('button',{name:'Create experiment & train'})).toBeTruthy();
 expect((screen.getByLabelText('Training episodes') as HTMLInputElement).max).toBe('1000');
 expect(screen.getByLabelText('Scenario')).toBeTruthy();
});
it('logs out directly from the dashboard and supports logging back in',async()=>{
 render(<MemoryRouter initialEntries={['/dashboard']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
 fireEvent.click(await screen.findByRole('button',{name:'Logout'}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/auth/logout'),expect.objectContaining({method:'POST'})));
 fireEvent.click(await screen.findByRole('button',{name:'Login'}));
 const dialog=screen.getByRole('dialog',{name:'Research account'});
 fireEvent.change(within(dialog).getByLabelText('Email'),{target:{value:user.email}});
 fireEvent.change(within(dialog).getByLabelText('Password'),{target:{value:'test-password-123'}});
 fireEvent.click(within(dialog).getByRole('button',{name:'Sign in'}));
 expect(await screen.findByRole('button',{name:'Logout'})).toBeTruthy();
 expect(screen.getByText('Welcome, Test researcher')).toBeTruthy();
});
