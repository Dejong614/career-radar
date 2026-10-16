const assert=require('node:assert/strict');
const {analyze}=require('../web/analytics.js');
const job=(track,skills)=>({track,skills:skills.map(name=>({name}))});
const a=analyze([
 job('traffic',['Python','SQL','Python']),job('traffic',['Python']),
 job('insurance',['Python','SQL']),job('av',['Python','SQL']),job('av',['C++'])
]);
assert.equal(a.sizes.traffic,2);
assert.equal(a.skillRanks.traffic.find(s=>s.name==='Python').count,2);
assert.equal(a.cross[0].name,'Python');
assert.equal(a.cross[0].coverage,3);
assert.equal(a.pairs.length,1);
assert.equal(a.pairs[0].count,3);
assert.equal(a.pairs[0].jaccard,3/4);
const empty=analyze([]);
assert.equal(empty.cross.length,0);
assert.equal(empty.pairs.length,0);
console.log('Analytics: deduplication, denominators, shared-skill ordering, Jaccard, empty states passed.');
