import React,{useEffect,useState} from 'react';
import {CalendarDays,LogOut,ShieldCheck} from 'lucide-react';
import {Account,useAuth} from './api';

const TIME_ZONE='Asia/Kolkata';
export function formatDashboardDate(date:Date){
 return new Intl.DateTimeFormat('en-IN',{timeZone:TIME_ZONE,day:'numeric',month:'long',year:'numeric'}).format(date);
}

export function DashboardDate(){
 const [now,setNow]=useState(()=>new Date());
 useEffect(()=>{const timer=setInterval(()=>setNow(new Date()),30000);return()=>clearInterval(timer)},[]);
 const weekday=new Intl.DateTimeFormat('en-IN',{timeZone:TIME_ZONE,weekday:'long'}).format(now);
 return <div className="dashboard-date"><span className="date-icon"><CalendarDays size={20}/></span><div><small>{weekday} · India Standard Time</small><time dateTime={now.toISOString()}>{formatDashboardDate(now)}</time></div></div>;
}

export function DashboardSession(){
 const {user,logout}=useAuth();
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 async function signOut(){
  setBusy(true);setError('');
  try{await logout()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <section className="panel dashboard-session" aria-label="Dashboard account and date">
  <div className="dashboard-identity"><ShieldCheck size={20}/><div><strong>{user?`Welcome, ${user.name}`:'Your pricing research workspace'}</strong><small>{user?`Logged in as ${user.email}`:'Log in to view your saved experiments and results.'}</small></div></div>
  <div className="dashboard-session-actions"><DashboardDate/>{user?<button className="button dashboard-logout" onClick={signOut} disabled={busy}><LogOut size={15}/>{busy?'Logging out…':'Logout'}</button>:<Account label="Login"/>}</div>
  {error&&<div className="error-box" role="alert">Unable to log out: {error}</div>}
 </section>;
}
