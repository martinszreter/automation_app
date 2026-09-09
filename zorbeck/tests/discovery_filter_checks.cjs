const assert = require('node:assert/strict');
const { filterProperties } = require('../static/discovery-core.js');
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
