/*
  Funciones utilitarias de ECG.
  - RATES: frecuencias de muestreo soportadas.
  - sampleBounds: devuelve el número mínimo/máximo de muestras según fs.
  - validatePatient: validación básica de la información del paciente.
  - bmi: cálculo del índice de masa corporal.
  - convolution: convolución discreta usada para filtrado.
  - simulate: genera señal ECG sintética para modo simulación.
  - intervalMs: ayuda a calcular intervalos en milisegundos.
  - captureDiagnostics: diagnóstico sencillo de valores crudos del ADC.
*/
export const RATES = [100, 250, 500];
export const sampleBounds = fs => [2 * fs, 60 * fs];
export function validatePatient(p) {
  return p.name.trim().length > 0 && p.name.trim().length <= 160 && !/[\x00-\x1f\x7f]/.test(p.name) && p.age !== '' && Number.isInteger(Number(p.age)) && Number(p.age) >= 0 && Number(p.age) <= 130 && p.weight !== '' && Number(p.weight) >= 0.1 && Number(p.weight) <= 500 && p.height !== '' && Number(p.height) >= 1 && Number(p.height) <= 270;
}
export function bmi(p) { return Number(p.weight) > 0 && Number(p.height) > 0 ? Number(p.weight) / (Number(p.height) / 100) ** 2 : null; }
// Same full discrete convolution as proyecto.py, avoiding iterations outside h.
export function convolution(x, h) {
  if (!x.length || !h.length) return [];
  return Array.from({length: x.length+h.length-1}, (_, n) => {
    let sum = 0;
    for (let k = Math.max(0,n-h.length+1); k <= Math.min(n,x.length-1); k++) sum += x[k]*h[n-k];
    return sum;
  });
}
export function simulate(samples, fs) {
  const time = Array.from({length:samples}, (_, i) => i/fs);
  const g = (p, c, w) => Math.exp(-0.5*((p-c)/w)**2);
  const raw = time.map(t => {
    const p=t%0.8;
    return 0.12*g(p,.16,.035)-0.13*g(p,.295,.012)+1.1*g(p,.33,.014)-.25*g(p,.37,.014)+.27*g(p,.55,.06)+.045*Math.sin(2*Math.PI*.35*t)+.045*Math.sin(2*Math.PI*27*t)+.025*Math.cos(2*Math.PI*43*t);
  });
  const kernel=Array(10).fill(.1);
  // Causal output at the original timestamps. Startup transient left undefined;
  // full convolution tail excluded because it is not a recorded time interval.
  const filtered=convolution(raw,kernel).slice(0,samples).map((v,i)=>i<9?null:v);
  return {time,raw,filtered,fs,samples,duration:samples/fs,mode:'simulation'};
}
export function intervalMs(a,b) { return Math.abs(b-a)*1000; }

// Observable capture diagnostics, not a clinical quality score or safety check.
export function captureDiagnostics(raw=[],lead=[]){
  if(!raw.length)return null;
  let min=Infinity,max=-Infinity,low=0,high=0;
  for(const v of raw){min=Math.min(min,v);max=Math.max(max,v);if(v===0)low++;if(v===1023)high++;}
  const reported=lead.filter(v=>v===0||v===1).length;
  const disconnected=lead.filter(v=>v===1).length;
  return {min,max,peakToPeak:max-min,low,high,reported,disconnected,percent:reported?100*disconnected/reported:null};
}
