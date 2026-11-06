const fs=require('fs'),vm=require('vm'),assert=require('assert');const source=fs.readFileSync('dist/music.js','utf8');const ctx={};vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf(' function validEpisodeDate'),source.indexOf(' // Stable daily album sampling')),ctx);
const one={artist:'Performer One',album:'Aangenaam Klassiek 2001 (Disc 1)',compilation:1,disc:'1/2',track:'2',title:'First'},two={...one,artist:'Performer Two',album:'Aangenaam Klassiek 2001 (Disc2)',disc:'2/2',track:'1'};
assert.equal(ctx.albumKey(one),ctx.albumKey(two));assert.equal(ctx.albumLabel(one),'Aangenaam Klassiek 2001');assert.equal(ctx.albumArtist(one),'Various Artists');assert(ctx.albumOrder(one,two)<0);
assert.equal(ctx.albumKey({...one,compilation:0,albumArtist:'Album Artist'}),ctx.albumKey({...two,compilation:0,albumArtist:'Album Artist'}));assert.notEqual(ctx.albumKey({...one,compilation:0}),ctx.albumKey({...two,compilation:0}));assert.notEqual(ctx.albumKey({...one,album:'Greatest Hits',albumArtist:'Artist A'}),ctx.albumKey({...one,album:'Greatest Hits',albumArtist:'Artist B'}));assert.equal(ctx.albumKey({...one,artist:"Dad's Army",album:'1974.01.28'}),ctx.albumKey({...one,artist:"Dad's Army",album:'1974.02.04'}));assert.equal(ctx.albumTitle({...one,album:'Discography 2001'}),'Discography 2001');console.log('Compilation, album artist, multiple-disc ordering, separate releases and episode grouping: passed');

const compact={artist:'Kenneth Horne',album:'070468',year:'1968',title:'Round the Horne'};
assert.equal(ctx.episodeDate(compact),'1968-04-07');
assert.equal(ctx.albumKey(compact),ctx.albumKey({...compact,album:'240368'}));
assert.equal(ctx.albumKey(compact),ctx.albumKey({...compact,album:'67-06-11 s03e18',year:'1967'}));
assert.equal(ctx.episodeDate({...compact,year:''}),'');
assert.equal(ctx.episodeDate({...compact,year:'1967'}),'');
assert.equal(ctx.episodeDate({...compact,album:'310268'}),'');
assert(ctx.albumOrder({...compact,album:'240368'},compact)<0);
console.log('Compact dates, season/episode labels, corroborating years and invalid numeric albums: passed');

const radio={artist:'Round The Horne',album:'April 10th, 1966',title:'Episode',year:'1966'};
assert.equal(ctx.episodeDate(radio),'1966-04-10');
assert.equal(ctx.albumKey(radio),ctx.albumKey({...radio,artist:'Round the horne',album:'April 30, 1967'}));
assert.equal(ctx.albumKey(radio),ctx.albumKey({...radio,artist:'Round The Horne - BBC',album:'from BBC tape RTH 9'}));
assert.equal(ctx.albumKey(radio),ctx.albumKey({...compact,title:'Round the Horne Vol8 Side2'}));
assert.equal(ctx.albumKey(radio),ctx.albumKey({...radio,album:'May b9th, 1965'}));
assert.equal(ctx.episodeDate({...radio,album:'February 31st, 1966'}),'');
assert.equal(ctx.episodeDate({...radio,album:'10th April 1966'}),'1966-04-10');
assert.equal(ctx.albumLabel(radio),'Round the Horne');
assert.notEqual(ctx.albumKey(radio),ctx.albumKey({...compact,title:'Different programme'}));
console.log('Written dates, programme aliases, malformed known-series dates and unrelated programme isolation: passed');

const mix={album:'2000 Alternative',artist:'Butterfly',title:'Crazy Town',compilation:0,albumArtist:''};
assert.equal(ctx.albumKey(mix),ctx.albumKey({...mix,artist:'Bent'}));
assert.equal(ctx.albumArtist(mix),'Various Artists');
assert.equal(ctx.albumKey({...mix,album:'2000 Dance - Techno'}),ctx.albumKey({...mix,album:'2000 Dance - Techno',artist:'Janet Jackson'}));
assert.notEqual(ctx.albumKey({...mix,album:'Greatest Hits'}),ctx.albumKey({...mix,album:'Greatest Hits',artist:'Another Artist'}));
assert.notEqual(ctx.albumKey({...mix,albumArtist:'Known Album Artist'}),ctx.albumKey(mix));
assert.equal(ctx.albumArtist({...mix,album:'2000'}),'Butterfly');
console.log('Missing compilation flags on year/genre mixes, explicit album artists and unrelated same-title albums: passed');

assert.equal(ctx.albumKey({...mix,album:'2000 Mellow'}),ctx.albumKey({...mix,album:'2000 Mellow',artist:'Bye Bye Bye'}));
const dre={album:'2001',artist:'Dr Dre',albumArtist:'Dr. Dre',title:'The Next Episode'};
assert.equal(ctx.albumKey(dre),ctx.albumKey({...dre,albumArtist:'Dr. Dre Featuring Eminem'}));
assert.equal(ctx.albumKey(dre),ctx.albumKey({...dre,albumArtist:'Dr Dre feat. Eminem'}));
assert.notEqual(ctx.albumKey(dre),ctx.albumKey({...dre,albumArtist:'Another Artist'}));
console.log('Mellow collections and featured-credit album splits: passed');

for(const album of ["60's Pop","60’s R&b","60s Rock","70's Classic Rock","70's Disco","90's Alternative (Female)","90's Rock (Hard)"]){
 assert.equal(ctx.albumKey({...mix,album}),ctx.albumKey({...mix,album,artist:'Another track artist'}),album);
 assert.equal(ctx.albumArtist({...mix,album}),'Various Artists');
}
assert.notEqual(ctx.albumKey({...mix,album:'Greatest Hits'}),ctx.albumKey({...mix,album:'Greatest Hits',artist:'Another artist'}));
console.log('Decade collections, apostrophe variants, classic rock and collection subtitles: passed');

const soundtrack={...mix,album:'American Graffiti',inferredCompilation:true};
assert.equal(ctx.albumKey(soundtrack),ctx.albumKey({...soundtrack,artist:'Beach Boys'}));
assert.notEqual(ctx.albumKey({...soundtrack,inferredCompilation:false}),ctx.albumKey({...soundtrack,inferredCompilation:false,artist:'Beach Boys'}));
console.log('Shared-cover compilation evidence groups the soundtrack: passed');

assert.equal(ctx.albumKey({...mix,album:'Anthology 2',artist:'Beatles',albumArtist:'The Beatles'}),ctx.albumKey({...mix,album:'Anthology 2',artist:'Beatles',albumArtist:''}));
console.log('Leading The in artist identity does not split albums: passed');

const absolute={...mix,album:'Absolute Hits Collection',artist:'All-4-One',albumArtist:'All-4-One',inferredCompilation:true};
assert.equal(ctx.albumKey(absolute),ctx.albumKey({...absolute,artist:'Mark Morrison',albumArtist:'Various Artists',inferredCompilation:false}));
assert.equal(ctx.albumArtist(absolute),'Various Artists');
assert.equal(ctx.albumArtist({...absolute,inferredCompilation:false}),'All-4-One');
console.log('Shared-cover evidence overrides per-track album-artist tags: passed');
