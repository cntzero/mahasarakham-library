const fs=require('fs'),vm=require('vm'),assert=require('assert'),cp=require('child_process');
const source=fs.readFileSync('dist/music.js','utf8'),ctx={};vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf(' function validEpisodeDate'),source.indexOf(' // Stable daily album sampling')),ctx);
const base={artist:'Artist',title:'Track',album:'Release',albumArtist:'',compilation:0,disc:'',track:'1',year:'',originalName:''};
const rows=[{}, {album:'Release (Disc 2 of 3)'},{album:'Release [CD2]'},{album:'Release - Disk 2'},{album:'60’s Pop'},{album:'2000 Mellow'}, {album:'2001',albumArtist:'The Beatles Featuring Guest'}, {album:'American Graffiti',inferredCompilation:true}, {artist:'Round The Horne',album:'April 10th, 1966'}, {artist:'Round The Horne - BBC',album:'from tape',originalName:'67-06-11 s03e18.mp3'}, {artist:'Kenneth Horne',title:'Round the Horne Vol8 Side2',album:'070468',year:'1968'}, {album:'1966-02-31'}, {album:'67-06-11 s03e18',year:'1967'}, {album:'07/06/1967'}, {album:'東京',artist:'日本語'}, {album:'Release',albumArtist:'Dr. Dre feat. Guest'}, {album:'Release',disc:'2/3'}, {album:'Release',disc:'0'}].map(r=>({...base,...r}));
const py="import sys,json;sys.path.insert(0,'sites/mahasarakham-library/upload-service');import music,music_grouping;rows=json.load(sys.stdin);print(json.dumps(music_grouping.annotate(rows,music.inferred_compilation)))";
const result=cp.spawnSync('python',['-c',py],{input:JSON.stringify(rows),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});if(result.status!==0)throw Error(result.stderr);
const backend=JSON.parse(result.stdout);
for(let i=0;i<rows.length;i++){
 assert.equal(backend[i].groupKey,ctx.albumKey(rows[i]),'key '+JSON.stringify(rows[i]));
 assert.equal(backend[i].groupLabel,ctx.albumLabel(rows[i]));
 assert.equal(backend[i].displayAlbumArtist,ctx.albumArtist(rows[i]));
 assert.equal(backend[i].sortDisc,ctx.discNumber(rows[i]));
 assert.equal(backend[i].sortEpisodeDate,ctx.episodeSortDate(rows[i]));
}
console.log('Shared server/browser grouping parity across '+rows.length+' release, episode, Unicode and disc fixtures: passed');
