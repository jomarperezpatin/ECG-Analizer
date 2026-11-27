import test from 'node:test';
import assert from 'node:assert/strict';
import {convolution,simulate,validatePatient,bmi,intervalMs,sampleBounds} from '../src/ecg.js';
test('convolución discreta completa',()=>assert.deepEqual(convolution([1,2,3],[1,1]),[1,3,5,3]));
test('tiempo y muestras coherentes en todas las tasas',()=>{for(const fs of [100,250,500]){const s=simulate(fs*6,fs);assert.equal(s.raw.length,fs*6);assert.equal(s.filtered.length,s.raw.length);assert.equal(s.time[1],1/fs);assert.equal(s.duration,6);assert.equal(s.filtered[0],null);assert.ok(Number.isFinite(s.filtered[9]));assert.deepEqual(sampleBounds(fs),[fs*2,fs*60]);}});
test('formulario paciente y cálculo IMC',()=>{const p={name:'Paciente ficticio',age:'25',weight:'75',height:'175'};assert.equal(validatePatient(p),true);assert.equal(validatePatient({...p,age:''}),false);assert.equal(validatePatient({...p,weight:'0'}),false);assert.equal(bmi(p).toFixed(2),'24.49');});
test('intervalo en milisegundos',()=>assert.ok(Math.abs(intervalMs(.2,1)-800)<1e-8));

import {captureDiagnostics} from '../src/ecg.js';
test('capture diagnostics use real sample values and do not infer LO if absent',()=>{
  assert.deepEqual(captureDiagnostics([0,300,1023,700],[1,0,1,0]),{min:0,max:1023,peakToPeak:1023,low:1,high:1,reported:4,disconnected:2,percent:50});
  assert.equal(captureDiagnostics([512],[]).percent,null);
  assert.equal(captureDiagnostics([],[]),null);
});

test('nombre completo, código y validación de longitud',()=>{const p={name:'Ana María Pérez',age:'25',weight:'75',height:'175'};assert.equal(validatePatient(p),true);assert.equal(validatePatient({...p,name:'EXP-001'}),true);for(const name of ['   ','A'.repeat(161),'Ana\nPérez'])assert.equal(validatePatient({...p,name}),false);});
