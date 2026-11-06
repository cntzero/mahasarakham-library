'use strict';
// Common controls for every Daily Discoveries shelf. Page scripts supply content only.
document.querySelectorAll('.discovery-landscape').forEach(root=>{
 const shelf=root.querySelector('.discovery-shelf');if(!shelf)return;
 const sync=()=>{const previous=root.querySelector('.discovery-arrow.previous'),next=root.querySelector('.discovery-arrow.next');if(previous)previous.disabled=shelf.scrollLeft<=1;if(next)next.disabled=shelf.scrollLeft+shelf.clientWidth>=shelf.scrollWidth-2;};
 const wire=()=>{for(const [selector,direction] of [['.discovery-arrow.previous',-1],['.discovery-arrow.next',1]]){const button=root.querySelector(selector);if(button)button.onclick=()=>shelf.scrollBy({left:direction*shelf.clientWidth*.8,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}sync();};
 const surprise=root.querySelector('.discovery-caption button');if(surprise)surprise.addEventListener('click',()=>requestAnimationFrame(()=>{shelf.scrollTo({left:0,behavior:'instant'});sync();}));
 shelf.addEventListener('scroll',sync,{passive:true});window.addEventListener('resize',sync);
 let pending=false;new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;wire();});}}).observe(root,{childList:true,subtree:true});
 wire();
});
