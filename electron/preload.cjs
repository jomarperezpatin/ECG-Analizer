const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('ecgDesktop', {
  backup: (action, params) => ipcRenderer.invoke('ecg:backup', action, params),
  services: (action) => ipcRenderer.invoke('ecg:services', action),
  backend: (action, params) => ipcRenderer.invoke('ecg:backend', action, params),
  getPower: () => ipcRenderer.invoke('ecg:power'),
  onPowerChange: (callback) => {
    const handler = (_event, status) => callback(status);
    ipcRenderer.on('ecg:power-change', handler);
    return () => ipcRenderer.removeListener('ecg:power-change', handler);
  }
});
