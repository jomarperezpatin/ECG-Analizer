const {spawn,execFile}=require('node:child_process');
const {randomBytes}=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const {promisify}=require('node:util');
const run=promisify(execFile);
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function makeServices(app){
  let child, base, token, pending, lastError='', closing=false;
  const root=path.join(__dirname,'..');
  const status=()=>({python:base?'online':pending?'starting':'offline',error:lastError});
  async function request(route,options={}){
    if(!base) throw new Error(lastError||'Python aún no está disponible.');
    return fetch(base+route,{...options,headers:{...options.headers,'X-ECG-Token':token}});
  }
  async function start(){
    if(closing) throw Error('La aplicación se está cerrando');
    if(base)return;
    if(pending)return pending;
    pending=(async()=>{
      lastError=''; token=randomBytes(32).toString('hex');
      const executable=app.isPackaged?path.join(process.resourcesPath,'backend','ecg-backend.exe'):path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
      const args=app.isPackaged?[]:[path.join(root,'backend','launch.py')];
      if(!fs.existsSync(executable))throw Error('No se encontró el backend. Ejecuta instalar-desarrollo.ps1 o revisa el instalador.');
      const logDir=path.join(app.getPath('userData'),'logs');fs.mkdirSync(logDir,{recursive:true});
      const stream=fs.createWriteStream(path.join(logDir,'backend.log'),{flags:'w'});stream.on('error',()=>{});
      const p=spawn(executable,args,{cwd:app.getPath('userData'),env:{...process.env,ECG_API_TOKEN:token,PYTHONUNBUFFERED:'1'},windowsHide:true,stdio:['pipe','pipe','pipe']});child=p; p.stdin.on('error',()=>{});
      let output='',candidate='';
      p.stdout.on('data',chunk=>{stream.write(chunk);output=(output+chunk.toString()).slice(-4096);const m=output.match(/ECG_PORT=(\d+)/);if(m)candidate='http://127.0.0.1:'+m[1];});
      p.stderr.on('data',chunk=>stream.write(chunk));
      p.on('error',e=>{lastError=e.message;});
      p.on('close',code=>{stream.end();if(child===p){child=null;base=null;lastError=closing?'':'Python finalizó ('+code+'). Revisa los registros.';}});
      const until=Date.now()+30000;
      while(Date.now()<until&&!closing&&child===p){
        if(candidate){try{const r=await fetch(candidate+'/api/health',{headers:{'X-ECG-Token':token},signal:AbortSignal.timeout(1000)});const d=await r.json();if(r.ok&&d.status==='ok'&&d.version==='1.0.0'){base=candidate;return;}}catch{}}
        await wait(200);
      }
      if(child===p)p.kill();throw Error(lastError||'Python no inició. Revisa logs/backend.log.');
    })().catch(e=>{lastError=e.message;throw e;}).finally(()=>{pending=null;});
    return pending;
  }
  async function mongo(){
    // Reuse the user's existing database. Never silently create a second instance.
    const check=async()=>{try{return (await request('/api/storage/health',{signal:AbortSignal.timeout(4000)})).ok;}catch{return false;}};
    if(await check())return {ok:true,message:'MongoDB disponible'};
    if(process.platform!=='win32'||process.env.ECG_MONGO_URI||process.env.MONGODB_URI)return {ok:false,message:'Comprueba tu servicio MongoDB configurado.'};
    const sc=path.join(process.env.SystemRoot||'C:\\Windows','System32','sc.exe');
    const service=process.env.ECG_MONGO_SERVICE||'MongoDB';
    if(!/^[A-Za-z0-9_.-]{1,80}$/.test(service))return {ok:false,message:'Nombre del servicio MongoDB inválido.'};
    try{await run(sc,['start',service],{windowsHide:true,timeout:8000});}catch{}
    for(let i=0;i<3&&!closing;i++){if(await check())return {ok:true,message:'MongoDB disponible'};await wait(500);}
    return {ok:false,message:'MongoDB no disponible. Inicia el servicio de Windows si requiere permisos; no se ha cambiado la base de datos.'};
  }
  async function stop(){closing=true;const p=child;base=null;if(p){const closed=new Promise(r=>p.once('close',r));p.stdin.end();await Promise.race([closed,wait(6500)]);if(child===p){p.kill();await Promise.race([closed,wait(1500)]);}}}
  return {start,request,mongo,stop,status};
}
module.exports={makeServices};
