const fs=require('fs'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'../dist');
for(const page of ['index.html','music.html','knowledge.html']){
 const html=fs.readFileSync(path.join(root,page),'utf8');
 assert.equal((html.match(/href="discovery\.css\?v=shared-2"/g)||[]).length,1,page+' must load the same shared stylesheet once');
 assert.equal((html.match(/src="discovery\.js\?v=shared-2"/g)||[]).length,1,page+' must load the same shared controller once');
 assert(/class="hero discovery-hero"/.test(html),page+' must use the shared hero');
 assert(/class="landscape discovery-landscape"/.test(html),page+' must use the shared panel');
 assert(/class="(?:shelf )?discovery-shelf"/.test(html),page+' must use the shared scroll lane');
 assert(/class="(?:stamp )?discovery-caption"/.test(html),page+' must use the shared caption');
 const shared=html.indexOf('href="discovery.css');
 for(const css of ['browse.css','music.css','knowledge.css']){const index=html.indexOf('href="'+css);if(index>=0)assert(index<shared,page+' must load page styles before shared component styles');}
}
const musicCss=fs.readFileSync(path.join(root,'music.css'),'utf8');assert(!/\.music-hero\s*\{|\.music-discovery\s*\{|\.discovery-caption\s*\{|\.discovery-arrow\s*\{/.test(musicCss),'No duplicated Music discovery geometry');
const shared=fs.readFileSync(path.join(root,'discovery.css'),'utf8');assert(shared.includes('grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)'));assert(shared.includes('padding:64px 0 45px'));assert(shared.includes('height:315px'));assert(shared.includes('@media(max-width:650px)'));
assert(fs.readFileSync(path.join(root,'browse.js'),'utf8').includes('discovery-item discovery-book'));
assert(fs.readFileSync(path.join(root,'music.js'),'utf8').includes('discovery-item discovery-record'));
assert(fs.readFileSync(path.join(root,'knowledge-discoveries.js'),'utf8').includes('discovery-item discovery-site'));
console.log('Books, Music and Knowledge share hero, panel, scroll lane, controls, CSS order and breakpoints; duplicate Music geometry removed: passed');

const repair=fs.readFileSync(path.join(root,'layout-repair.css'),'utf8');assert(!repair.includes('.repair-catalog .hero,.repair-catalog #home-hero{display:none!important}'),'Catalog styling must not hide shared Daily Discoveries');assert(repair.includes('.hero:not(.discovery-hero)'),'Shared discovery heroes must remain visible on catalog pages');
