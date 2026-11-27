const { app, BrowserWindow, ipcMain, powerMonitor, dialog } = require('electron');
app.disableHardwareAcceleration();
const path = require('node:path');
const iconPath=path.join(__dirname,'assets','ecg.ico');
const {makeServices}=require('./services.cjs');
const services=makeServices(app);
let quitting=false, quitReady=false;
const primaryInstance=app.requestSingleInstanceLock();
if(!primaryInstance) app.quit();
app.on('second-instance',()=>{if(mainWindow&&!mainWindow.isDestroyed()){if(mainWindow.isMinimized())mainWindow.restore();mainWindow.focus();}});
let mainWindow;
let activeBench;
async function stopBench(){ if(activeBench) { try { await services.request("/api/bench/stop",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:activeBench}),signal:AbortSignal.timeout(2000)}); } catch {} } }
const isDev = process.argv.includes('--dev');
function powerStatus() {
  try { return powerMonitor.isOnBatteryPower() ? 'battery' : 'ac-or-desktop'; }
  catch { return 'unknown'; }
}
function createWindow(hidden=false) {
  mainWindow = new BrowserWindow({ width: 1440, height: 980, minWidth: 800, minHeight: 600,
    backgroundColor: '#0b1420', autoHideMenuBar: true, show:!hidden, icon:iconPath,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true } });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  mainWindow.webContents.on('will-navigate', (event) => event.preventDefault());
  return isDev ? mainWindow.loadURL('http://127.0.0.1:5173') : mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
}
function createSplash(){
  const splash=new BrowserWindow({width:480,height:310,resizable:false,frame:false,closable:false,center:true,alwaysOnTop:true,backgroundColor:'#0b1420',icon:iconPath,webPreferences:{preload:path.join(__dirname,'splash-preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  splash.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  splash.webContents.on('will-navigate',e=>e.preventDefault());
  return {window:splash,ready:splash.loadFile(path.join(__dirname,'splash.html'))};
}
async function boot(){
  const splash=createSplash();
  const stage=(label,percent)=>{if(!splash.window.isDestroyed())splash.window.webContents.send('ecg:splash',{label,percent});};
  const load=createWindow(true).catch(e=>console.error('Interfaz:',e.message));
  try{
    await splash.ready;
    stage('Iniciando motor Python y FastAPI…',30);
    await services.start();
    stage('Verificando MongoDB local…',65);
    const db=await services.mongo();
    stage(db.ok?'Servicios disponibles':'MongoDB no disponible · revisa Configuración',90);
  }catch(e){console.error('Inicio:',e.message);stage('Inicio parcial · revisa Configuración',90);}
  finally{await load; if(mainWindow&&!mainWindow.isDestroyed()){mainWindow.show();mainWindow.focus();}if(!splash.window.isDestroyed())splash.window.destroy();}
}
app.whenReady().then(() => {
  if(!primaryInstance)return;
  ipcMain.handle('ecg:services', async (_event,action)=>{if(action==='retry'){await services.start();return services.mongo();}return services.status();});
  ipcMain.handle('ecg:power', () => powerStatus());
  let archiveBusy=false;
  ipcMain.handle('ecg:backup',async(event,action,params)=>{
    if(!mainWindow||event.sender!==mainWindow.webContents)throw new Error('Origen no permitido');
    if(!['create','restore','select'].includes(action))throw new Error('Operación no permitida');
    if(archiveBusy||activeBench)throw new Error('Finaliza la operación actual.');
    archiveBusy=true;
    try{
      await services.start();
      let payload;
      if(action==='create'){
        const result=await dialog.showSaveDialog(mainWindow,{title:'Guardar respaldo ECG (sin cifrar)',defaultPath:'ECG-'+new Date().toISOString().replace(/[:.]/g,'-')+'.ecgbackup',filters:[{name:'Respaldo ECG',extensions:['ecgbackup']}]});
        if(result.canceled||!result.filePath)return {cancelled:true};
        payload={path:result.filePath.toLowerCase().endsWith('.ecgbackup')?result.filePath:result.filePath+'.ecgbackup'};
      }else if(action==='restore'){
        const result=await dialog.showOpenDialog(mainWindow,{title:'Restaurar en una base independiente',properties:['openFile'],filters:[{name:'Respaldo ECG',extensions:['ecgbackup']}]});
        if(result.canceled||!result.filePaths[0])return {cancelled:true};
        payload={path:result.filePaths[0]};
      }else payload={database:params?.database??null};
      const r=await services.request('/api/backup/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(300000)});
      const data=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Error de respaldo: HTTP '+r.status);
      return data;
    }finally{archiveBusy=false;}
  });
  ipcMain.handle('ecg:backend', async (_event, action, params) => {
    const routes = {health: '/api/health', ports: '/api/ports', simulate: '/api/ecg/simulate', analyze: '/api/ecg/analyze', benchStart:'/api/bench/start', benchStatus:'/api/bench/status', benchStop:'/api/bench/stop', storageHealth:'/api/storage/health', storageList:'/api/storage/list', storageSave:'/api/storage/save', storageGet:'/api/storage/get', storageImage:'/api/storage/image', storageDelete:'/api/storage/delete', storageExport:'/api/storage/export'};
    if (!Object.hasOwn(routes, action)) throw new Error('Operación no permitida');
    await services.start();
    const options = {signal: AbortSignal.timeout(['storageSave','storageExport'].includes(action)?30000:10000)};
    if (action === 'benchStart' && powerStatus() !== 'battery') throw new Error('Desconecta el cargador. Alimentación por batería requerida para adquisición física.');
    if (action === 'benchStatus' && powerStatus() !== 'battery') await stopBench();
    if (action === 'simulate' || action === 'analyze' || action.startsWith('bench')) {
      options.method = 'POST'; options.headers = {'Content-Type':'application/json'};
      options.body = JSON.stringify(action==='simulate'?{samples:params?.samples,fs:params?.fs}:action==='analyze'?{raw:params?.raw,fs:params?.fs,kind:params?.kind,window:params?.window,timestamps:params?.timestamps}:action==='benchStart'?{port:params?.port,samples:params?.samples,fs:params?.fs,confirmed_bench:params?.confirmed_bench===true,mode:params?.mode==='experimental'?'experimental':'bench',confirmed_experimental:params?.confirmed_experimental===true,protocol:params?.protocol==='numeric'?'numeric':'ecg1'}:{id:params?.id});
    }
    if (['storageSave','storageGet','storageImage','storageDelete','storageExport'].includes(action)) {
      options.method='POST'; options.headers={'Content-Type':'application/json'};
      options.body=JSON.stringify(action==='storageSave'?params:{id:params?.id});
    }
    const query=action==='storageExport'?'?fmt='+ (params?.format==='csv'?'csv':'pdf'):action==='storageList'?'?q='+encodeURIComponent(String(params?.q||'').slice(0,160)):'';
    let response;
    try { response = await services.request(routes[action]+query, options); }
    catch { throw new Error('Backend Python no disponible. Reintenta desde Configuración.'); }
    if (!response.ok) { const err=await response.json().catch(()=>({})); throw new Error(typeof err.detail==='string'?err.detail:'Backend: HTTP '+response.status); }
    const data = await response.json();
    if (action === 'health' && (data.version !== '1.0.0' || data.status !== 'ok')) throw new Error('Backend incompatible');
    if(action==='benchStart'){activeBench=data.id; if(powerStatus()!=='battery') await stopBench();}
    if(action==='benchStatus' && !['connecting','running'].includes(data.state) && data.id===activeBench) activeBench=null;
    return data;
  });
  for (const event of ['on-ac', 'on-battery', 'resume']) powerMonitor.on(event, () => {
    if(powerStatus()!=='battery') void stopBench();
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('ecg:power-change', powerStatus());
  });
  void boot();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) void createWindow().catch(e=>console.error(e.message)); });
});
app.on('before-quit',event=>{if(quitReady)return;event.preventDefault();if(quitting)return;quitting=true;void (async()=>{await stopBench();if(activeBench){for(let i=0;i<18;i++){try{const r=await services.request('/api/bench/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:activeBench}),signal:AbortSignal.timeout(500)});const d=await r.json();if(!['connecting','running'].includes(d.state))break;}catch{break;}await new Promise(r=>setTimeout(r,200));}}await services.stop();quitReady=true;app.quit();})();});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
