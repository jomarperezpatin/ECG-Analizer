/*
  Componente ECGChart – renderiza la señal ECG usando Plotly.
  Permite visualizar señales crudas y filtradas, seleccionar diferentes modos de vista,
  medir intervalos y exportar el gráfico como PNG.
*/
// ECGChart component: renders ECG signal plot using Plotly
import React,{useEffect,useRef,useState} from 'react';
import React,{useEffect,useRef,useState} from 'react';
import Plotly from 'plotly.js-dist-min';
import {intervalMs,captureDiagnostics} from './ecg.js';
export default function ECGChart({study,count,running}) {
  // Mapping of filter identifiers to human‑readable names
const filterNames={
  none:'Sin filtro',
  moving:'Media móvil',
  notch:'Notch 60 Hz',
  bandpass:'Paso banda 0.5–40 Hz',
  combined:'Notch + paso banda'
};
  const filterName=study?.filter_kind==='moving'||!study?.filter_kind?'Convolución · media móvil':(filterNames[study.filter_kind]||'Filtro histórico')+' (histórico)';
  const experimental=study?.mode==='experimental',bench=study?.mode==='bench',physical=experimental||bench,filename=experimental?'ECG_EXPERIMENTAL_NO_DIAGNOSTICO':bench?'ADC_BANCO_NO_CLINICO':'ECG_SIMULADO';
  const quality=physical?captureDiagnostics(study?.raw,study?.lead):null;
  const div=useRef(null), current=useRef(null), queue=useRef(Promise.resolve());
  const [view,setView]=useState('split'), [measuring,setMeasuring]=useState(false), [points,setPoints]=useState([]), [rev,setRev]=useState(0), [error,setError]=useState('');
  current.current={measuring};
  useEffect(()=>{setPoints([]);setMeasuring(false);setError('');},[study?.id,view]);
  useEffect(()=>{
    const el=div.current;
    if(!el || !study) return;
    let stale=false;
    const n=Math.min(count,study.samples), x=study.time.slice(0,n);
    const traces=[], split=view==='split';
    if(view!=='filtered') traces.push({x,y:study.raw.slice(0,n),type:'scatter',mode:'lines',name:'Original',line:{color:'#a9c9ed',width:1.4}});
    if(view!=='raw') traces.push({x,y:study.filtered.slice(0,n),type:'scatter',mode:'lines',name:'Procesada · '+filterName,...(split?{yaxis:'y2'}:{}),line:{color:'#49dfa8',width:1.6}});
    const axis={gridcolor:'#233e44',zerolinecolor:'#36515a',linecolor:'#405a65',tickfont:{color:'#a7bacb'},fixedrange:false};
    const shapes=points.map(p=>({type:'line',xref:'x',yref:'paper',x0:p,x1:p,y0:0,y1:1,line:{color:'#f4bf68',width:2,dash:'dash'}}));
    if(points.length===2)shapes.unshift({type:'rect',xref:'x',yref:'paper',x0:Math.min(...points),x1:Math.max(...points),y0:0,y1:1,fillcolor:'rgba(244,191,104,.10)',line:{width:0},layer:'below'});
    const layout={autosize:true,height:split?540:440,paper_bgcolor:'#101d29',plot_bgcolor:'#0a191b',font:{color:'#b9c9d7'},margin:{l:65,r:20,t:45,b:65},showlegend:true,legend:{orientation:'h',y:1.12},hovermode:'closest',dragmode:measuring?'pan':'zoom',uirevision:`${study.id}-${view}-${rev}`,xaxis:{...axis,title:study.timing==='nominal'?'Tiempo nominal (s)':'Tiempo (s)',rangeslider:{visible:!running,thickness:.12,bgcolor:'#142630'},range:[0,study.duration]},yaxis:{...axis,title:physical?(view==='filtered'?'Procesada (cuentas)':'ADC (cuentas, sin calibrar)'):(view==='filtered'?'Procesada (u.a.)':'Amplitud relativa (u.a.)'),...(split?{domain:[.56,1]}:{})},...(split?{yaxis2:{...axis,domain:[0,.44],anchor:'x',title:physical?'Procesada (cuentas)':'Procesada (u.a.)'}}:{}),shapes,annotations:[{xref:'paper',yref:'paper',x:1,y:1,xanchor:'right',yanchor:'top',text:experimental?(study.state==='complete'?'ECG EXPERIMENTAL · NO DIAGNÓSTICO':running?'ECG EXPERIMENTAL · CAPTURANDO':'CAPTURA EXPERIMENTAL INCOMPLETA'):bench?'ADC DE BANCO · NO ECG CLÍNICO':'ECG SIMULADO · NO CLÍNICO',showarrow:false,font:{size:11,color:'#f4bf68'},bgcolor:'#17242b'}]};
    queue.current=queue.current.catch(()=>{}).then(async()=>{
      if(stale||!el.isConnected)return;
      await Plotly.react(el,traces,layout,{responsive:true,displaylogo:false,scrollZoom:true,displayModeBar:true,modeBarButtonsToRemove:['select2d','lasso2d'],locale:'en',toImageButtonOptions:{format:'png',filename,scale:2}});
      if(stale||!el.isConnected)return;
      el.removeAllListeners('plotly_click');
      el.on('plotly_click', ev=>{if(!current.current.measuring)return; const t=Number(ev.points?.[0]?.x); if(Number.isFinite(t))setPoints(old=>old.length===1?[old[0],t]:[t]);});
    }).catch(e=>{if(!stale)setError(String(e.message||e));});
    return ()=>{stale=true;};
  },[study,count,running,view,measuring,points,rev]);
  useEffect(()=>{const el=div.current;return()=>{if(el)queue.current.finally(()=>Plotly.purge(el));};},[]);
  async function exportImage(){try{await Plotly.downloadImage(div.current,{format:'png',filename,scale:2});}catch(e){setError(String(e.message||e));}}
  return <section className="panel chart-panel"><div className="section-head"><div><span className="eyebrow">CANAL 1 · AD8232 {experimental?'(EXPERIMENTAL)':bench?'(BANCO)':'(VISTA PREVISTA)'}</span><h2>Monitor electrocardiográfico</h2></div><span className="tag">{experimental?'ECG EXPERIMENTAL':bench?'BANCO':'SIMULACIÓN'}</span></div>
    <div className="chart-tools"><div className="segmented">{[['split','Separadas'],['both','Ambas'],['raw','Original'],['filtered','Filtrada']].map(([v,l])=><button key={v} className={view===v?'selected':''} onClick={()=>setView(v)}>{l}</button>)}</div><button disabled={!study||running} className={measuring?'active':''} onClick={()=>{setMeasuring(!measuring);setPoints([]);}}>↔ Medir intervalo</button><button disabled={!study} onClick={()=>setRev(v=>v+1)}>Restablecer zoom</button><button disabled={!study||running||(experimental&&study.state!=='complete')} onClick={exportImage}>↓ PNG</button></div>
    {!study&&<div className="empty-chart"><span className="pulse">∿</span><strong>Sin señal adquirida</strong><span>Selecciona una modalidad para iniciar la adquisición.</span></div>}
    <div ref={div} className="plot" style={{display:study?'block':'none'}}/>
    {quality&&<div className="quality-grid" aria-label="Diagnóstico de adquisición"><div><small className="muted">ADC mínimo / máximo</small><strong>{quality.min} / {quality.max}</strong></div><div><small className="muted">Amplitud pico a pico</small><strong>{quality.peakToPeak} cuentas</strong></div><div><small className="muted">Extremos ADC (0 / 1023)</small><strong>{quality.low} / {quality.high}</strong></div><div><small className="muted">Avisos LO</small><strong>{quality.percent===null?'Sin datos':`${quality.disconnected}/${quality.reported} (${quality.percent.toFixed(1)}%)`}</strong></div></div>}
    {quality?.disconnected>0&&<p className="warn small">Se detectó LO alto. No interpretar esta señal como ECG. Las gráficas separadas tienen escalas independientes.</p>}
    {measuring&&<div className="measurement">{points.length<2?'Selecciona dos puntos de la curva para medir su separación temporal.':`A: ${points[0].toFixed(3)} s · B: ${points[1].toFixed(3)} s · Δt: ${intervalMs(...points).toFixed(1)} ms`}<button onClick={()=>setPoints([])}>Limpiar</button></div>}
    {error&&<p role="alert" className="warn">{error}</p>}
    <p className="muted small">Arrastra para ampliar, usa la rueda para zoom y la barra inferior para navegar. {study?.filter_kind&&study.filter_kind!=='moving'?'Procesamiento fuera de línea; pueden existir artefactos de borde.':`Media móvil causal: retardo de ${study?.delay_samples??4.5} muestras.`} {view==='split'?' Las dos gráficas usan escalas independientes y comparten el eje temporal.':''} No usar para medición clínica.</p>
  </section>;
}
