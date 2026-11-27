const {ipcRenderer}=require('electron');
window.addEventListener('DOMContentLoaded',()=>{
  ipcRenderer.on('ecg:splash',(_event,state)=>{
    document.getElementById('stage').textContent=String(state.label);
    document.getElementById('progress').value=Number(state.percent)||0;
  });
});
