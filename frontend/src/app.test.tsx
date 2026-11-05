// @vitest-environment jsdom
import React from 'react';
import {afterEach, beforeEach, describe, expect, it} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {App} from './main';
import {pages} from './pages';
beforeEach(()=>localStorage.clear());
afterEach(cleanup);
function open(path:string){return render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>)}
describe('approved navigation',()=>{
 for(const page of pages) it(`renders ${page.path}`,()=>{open(page.path);expect(screen.getByRole('heading',{level:1}).textContent).toBe(page.title);expect(screen.getByRole('link',{name:new RegExp(`^${page.title.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}( RL)?$`)}).getAttribute('aria-current')).toBe('page');});
 it('opens the dashboard at the root URL',()=>{open('/');expect(screen.getByRole('heading',{level:1}).textContent).toBe('Dashboard')});
 it('handles unknown URLs',()=>{open('/missing');expect(screen.getByRole('heading',{level:1}).textContent).toBe('Page not found')});
 it('navigates from the dashboard without reload',()=>{open('/dashboard');fireEvent.click(screen.getByRole('link',{name:'Build a market scenario'}));expect(screen.getByRole('heading',{level:1}).textContent).toBe('Market scenarios')});
 it('persists a color theme',()=>{open('/dashboard');fireEvent.click(screen.getByRole('button',{name:'Toggle color theme'}));expect(localStorage.getItem('pm-theme')).toBe('dark')});
 it('opens the sign-in dialog',()=>{open('/dashboard');fireEvent.click(screen.getByRole('button',{name:'Sign in'}));expect(screen.getByRole('dialog',{name:'Research account'})).toBeTruthy();expect(screen.getByLabelText('Password')).toBeTruthy()});
 it('does not render fabricated dashboard profits',()=>{open('/dashboard');expect(screen.getByText('Sign in to view your research results.')).toBeTruthy();expect(screen.getByText('Latest evaluation profit')).toBeTruthy()});
});
