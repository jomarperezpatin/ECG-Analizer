// Own the Vite server in this process; no shell and no accidental use of a foreign server.
const {spawn}=require('node:child_process');
const path=require('node:path');
const root=path.join(__dirname,'..');
let server,child,done=false;
async function stop(code=0){if(done)return;done=true;if(child&&child.exitCode===null)child.kill();if(server)await server.close();process.exitCode=code;}
process.on('SIGINT',()=>void stop());process.on('SIGTERM',()=>void stop());
(async()=>{try{const {createServer}=await import('vite');server=await createServer({root,server:{host:'127.0.0.1',port:5173,strictPort:true}});await server.listen();server.printUrls();if(done){await server.close();return;}const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;child=spawn(require('electron'),[root,'--dev'],{cwd:root,stdio:'inherit',windowsHide:false,env});child.on('exit',c=>void stop(c||0));child.on('error',e=>{console.error(e.message);void stop(1);});}catch(e){console.error(e.message);await stop(1);}})();
