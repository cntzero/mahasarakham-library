'use strict';
(()=>{
  const displayKey='maha-account-display';
  function clearDisplay(){try{sessionStorage.removeItem(displayKey);}catch{}}
  function rememberDisplay(session){try{if(session.enabled&&session.user)sessionStorage.setItem(displayKey,JSON.stringify({time:Date.now(),email:session.user.email,role:session.user.role}));else clearDisplay();}catch{}}
  const parsed=document.readyState==='loading'?new Promise(resolve=>document.addEventListener('DOMContentLoaded',resolve,{once:true})):Promise.resolve();

  if(!document.querySelector('link[href*="session.css"]')){const stylesheet=document.createElement('link');stylesheet.rel='stylesheet';stylesheet.href='/session.css?v=users-steady-5';document.head.append(stylesheet);}
  function controls(session,preview=false){
    if(!preview)delete document.documentElement.dataset.accountPreview;
    document.querySelector('[data-maha-session-bar]')?.remove();
    const reservedUsers=document.querySelector('[data-maha-users-link]');if(reservedUsers)reservedUsers.style.visibility='hidden';
    if(!session.enabled)return;
    const bar=document.createElement('div');bar.className='maha-session-bar';bar.dataset.mahaSessionBar='';bar.setAttribute('aria-label','Your library account');
    const identity=document.createElement('span');identity.className='maha-session-identity';identity.textContent=session.user?'Signed in as '+session.user.email:'Not signed in';
    const actions=document.createElement('div');actions.className='maha-session-actions';
    if(session.user){
      const role=document.createElement('span');role.className='maha-session-role';role.textContent=session.user.role==='super'?'Super user':'User';
      const account=document.createElement('a');account.href='login.html';account.textContent='Account';
      const logout=document.createElement('button');logout.type='button';logout.className='maha-logout';logout.textContent='Log out';
      const message=document.createElement('span');message.className='maha-session-message';message.setAttribute('role','status');
      logout.onclick=async()=>{logout.disabled=true;message.textContent='';try{const response=await fetch('/api/library/logout',{method:'POST',headers:{'Content-Type':'application/json','X-Maha-Upload':'1'},body:'{}',credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error();clearDisplay();window.MAHA_SESSION={enabled:true,user:null};window.MAHA_CAN_MANAGE=false;location.replace('login.html');}catch{message.textContent='Could not log out. Check the connection and try again.';logout.disabled=false;}};
      actions.append(role,account,logout,message);
      const nav=document.querySelector('header nav');
      if(!preview&&nav&&session.user.role==='super'){let users=reservedUsers;if(!users){users=document.createElement('a');users.href='access.html';users.textContent='Users';users.dataset.mahaUsersLink='';nav.append(users);}users.href='access.html';users.removeAttribute('aria-disabled');users.removeAttribute('tabindex');users.style.visibility='visible';}
    }else{const signIn=document.createElement('a');signIn.href='login.html';signIn.textContent='Sign in';actions.append(signIn);}
    bar.append(identity,actions);
    const readerHeader=document.getElementById('viewer')&&document.querySelector('header');
    if(readerHeader){bar.classList.add('maha-session-compact');readerHeader.append(bar);}else {const slot=document.getElementById('maha-session-slot');if(slot)slot.replaceChildren(bar);else document.body.prepend(bar);}
  }
  // Only display metadata is reused. Permissions always come from the fresh response.
  window.MAHA_CAN_MANAGE=false;
  try{const cached=JSON.parse(sessionStorage.getItem(displayKey)||'null');if(cached&&typeof cached.email==='string'&&cached.email.length<=320&&['super','user'].includes(cached.role)&&Number.isFinite(cached.time)&&Date.now()-cached.time>=0&&Date.now()-cached.time<300000){document.documentElement.dataset.accountPreview=cached.role;controls({enabled:true,user:{email:cached.email,role:cached.role}},true);}}catch{clearDisplay();}
  window.MAHA_SESSION_READY=fetch('/api/library/session',{credentials:'same-origin',cache:'no-store'}).then(async response=>{if(!response.ok)throw Error();const session=await response.json();await parsed;if(typeof session.enabled!=='boolean')throw Error();rememberDisplay(session);window.MAHA_SESSION=session;window.MAHA_CAN_MANAGE=!session.enabled||session.user?.role==='super';document.querySelectorAll('[data-super]').forEach(e=>e.hidden=!window.MAHA_CAN_MANAGE);controls(session);document.dispatchEvent(new Event('maha-session'));return session;}).catch(async()=>{await parsed;clearDisplay();controls({enabled:true,user:null});window.MAHA_CAN_MANAGE=false;window.MAHA_SESSION={enabled:true,user:null,unavailable:true};document.querySelectorAll('[data-super]').forEach(e=>e.hidden=true);document.dispatchEvent(new Event('maha-session'));return window.MAHA_SESSION;});
  window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
})();
