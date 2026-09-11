const assert = require('node:assert/strict');
const { filterProperties, inBounds, longitudeNear } = require('../static/discovery-core.js');
const catalog = [
  {id:'a',city:'Lisbon',country:'Portugal',type:'Apartment',region:'Europe',tag:'City living',price:385000},
  {id:'b',city:'Zug',country:'Switzerland',type:'House',region:'Europe',tag:'Nature',price:1250000},
  {id:'c',city:'Marbella',country:'Spain',type:'Villa',region:'Europe',tag:'Coast',price:595000}
];
assert.deepEqual(filterProperties(catalog,{query:'LISBON portugal'},[]).map(x=>x.id),['a']);
assert.deepEqual(filterProperties(catalog,{query:'',budget:600000,type:'Villa'},[]).map(x=>x.id),['c']);
assert.deepEqual(filterProperties(catalog,{market:'Switzerland'},[]).map(x=>x.id),['b']);
assert.deepEqual(filterProperties(catalog,{query:'Tokyo'},[]),[]);
assert.deepEqual(filterProperties(catalog,{saved:true},['c']).map(x=>x.id),['c']);
assert.deepEqual(filterProperties(catalog,{sort:'price-desc'},[]).map(x=>x.id),['b','c','a']);
assert.deepEqual(catalog.map(x=>x.id),['a','b','c']);
console.log('Discovery filters: location, budget, property type, empty, saved and sort checks passed.');

// Synthetic coordinates exercise countries without pretending they are production listings.
const points = [
  { id:'china', lat:39.9, lng:116.4, price:200, type:'Apartment' },
  { id:'thailand', lat:13.75, lng:100.5, price:100, type:'Apartment' },
  { id:'usa', lat:40.7, lng:-74, price:300, type:'House' },
  { id:'pacific-west', lat:0, lng:175, price:100 },
  { id:'pacific-east', lat:0, lng:-175, price:100 }
];
const china = { south:18, west:73, north:54, east:135 };
const thailand = { south:5.5, west:97, north:20.5, east:106 };
const usa = { south:24, west:-126, north:50, east:-66 };
const ids = (bounds, extra = {}, saved = []) => filterProperties(points, { bounds, ...extra }, saved).map(p => p.id);
assert.deepEqual(ids(china), ['china']);
assert.deepEqual(ids(thailand), ['thailand']);
assert.deepEqual(ids(usa), ['usa']);
assert.deepEqual(ids(usa, { budget:200 }), []);
assert.deepEqual(ids(usa, { type:'Apartment' }), []);
assert.deepEqual(ids(usa, { saved:true }, ['china']), []);
assert.deepEqual(ids(usa, { saved:true }, ['usa']), ['usa']);
assert.deepEqual(ids({ south:-10, west:170, north:10, east:-170 }), ['pacific-west','pacific-east']);
assert.deepEqual(ids({ south:-10, west:170, north:10, east:190 }), ['pacific-west','pacific-east']);
assert.deepEqual(ids({ south:-10, west:-190, north:10, east:-170 }), ['pacific-west','pacific-east']);
assert.deepEqual(ids({ south:-85, west:-360, north:85, east:360 }), points.map(p=>p.id));
assert.equal(inBounds({lat:18,lng:73}, china), true);
assert.equal(inBounds({lat:54,lng:135}, china), true);
assert.equal(inBounds({lat:55,lng:135}, china), false);
assert.equal(inBounds({lat:NaN,lng:135}, china), false);
assert.equal(longitudeNear(175, -179), -185);
assert.equal(longitudeNear(-175, 179), 185);
assert.equal(longitudeNear(116.4, 100), 116.4);
console.log('Worldwide map: regional results, price/type/saved filters, date-line wrapping, world copies and boundary checks passed.');
