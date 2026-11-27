/*
  Componente principal de la aplicación ECG Analyzer.
  Gestiona el estado, la interacción con el backend (Electron/Python)
  y renderiza las pestañas: monitor, historial y configuración.
*/
import React, { useEffect, useRef, useState } from 'react';

/* Sub‑componentes de la UI */
import ECGChart from './ECGChart.jsx';
import FrequencyAnalysis from './FrequencyAnalysis.jsx';

/* Constantes y utilidades */
import { RATES, sampleBounds, validatePatient, bmi } from './ecg.js';

/* Plantilla vacía de paciente */
const blank = { name: '', age: '', weight: '', height: '' };
const modeLabel = { bench: 'Banco / no clínico', experimental: 'ECG experimental / no diagnóstico', simulation: 'Simulación' };
const numberFormat = new Intl.NumberFormat('es-MX');
const powerLabel = { battery: 'Batería detectada', 'ac-or-desktop': 'Corriente o equipo de escritorio', unknown: 'Estado no disponible' };

export default function App() {
  // ----- Estado principal ----------------------------------------------------
  const [patient, setPatient] = useState(blank),
        [fs, setFs] = useState(100),
        [samples, setSamples] = useState(1000),
        [draft, setDraft] = useState('1000');
  const [tab, setTab] = useState('monitor'),
        [power, setPower] = useState('unknown'),
        [dialog, setDialog] = useState(null),
        [study, setStudy] = useState(null),
        [count, setCount] = useState(0),
        [running, setRunning] = useState(false),
        [records, setRecords] = useState([]),
        [saved, setSaved] = useState(false),
        [message, setMessage] = useState('');
  const [backend, setBackend] = useState('checking'),
        [ports, setPorts] = useState([]),
        [portError, setPortError] = useState(''),
        [busy, setBusy] = useState(false);
  const [port, setPort] = useState(''),
        [confirmed, setConfirmed] = useState(false),
        [benchId, setBenchId] = useState(null),
        [physicalMode, setPhysicalMode] = useState('bench'),
        [protocol, setProtocol] = useState('numeric');
  const [dbStatus, setDbStatus] = useState('checking'),
        [historyError, setHistoryError] = useState(''),
        [search, setSearch] = useState(''),
        [more, setMore] = useState(false),
        [patientId, setPatientId] = useState(null),
        [processing, setProcessing] = useState(false);
  const [preview, setPreview] = useState(null),
        [serviceMessage, setServiceMessage] = useState('');
  const [dbName, setDbName] = useState(''),
        [backupMessage, setBackupMessage] = useState(''),
        [restoredDb, setRestoredDb] = useState(null),
        [usingRestored, setUsingRestored] = useState(false);
  const clock = useRef(0),
        timer = useRef(null),
        [min, max] = sampleBounds(fs),
        duration = samples / fs,
        valid = validatePatient(patient),
        mass = bmi(patient);

  // ----- Funciones auxiliares -------------------------------------------------
  async function refreshPower() {
    try { setPower(await window.ecgDesktop?.getPower() || 'unknown'); }
    catch { setPower('unknown'); }
  }

  async function checkBackend() {
    try { await window.ecgDesktop.backend('health'); setBackend('online'); }
    catch { setBackend('offline'); }
    try { const r = await window.ecgDesktop.backend('storageHealth'); setDbName(r.database); setDbStatus('online'); }
    catch { setDbStatus('offline'); }
  }

  async function loadHistory(q = search) {
    setBusy(true); setHistoryError('');
    try {
      const data = await window.ecgDesktop.backend('storageList', { q });
      setRecords(data.records); setMore(data.more); setDbStatus('online');
    } catch (e) {
      setHistoryError(String(e.message || e)); setRecords([]); setMore(false);
    } finally { setBusy(false); }
  }

  // ----- Efectos ------------------------------------------------------------
  useEffect(() => { if (tab === 'history') void loadHistory(''); }, [tab]);
  useEffect(() => { checkBackend(); const id = setInterval(checkBackend, 5000); return () => clearInterval(id); }, []);
  useEffect(() => { refreshPower(); const off = window.ecgDesktop?.onPowerChange(setPower); return () => off?.(); }, []);
  useEffect(() => {
    if (!running || !study || study.mode !== 'simulation') return;
    const tick = () => {
      const n = Math.min(study.samples, Math.floor((performance.now() - clock.current) * study.fs / 1000));
      setCount(n);
      if (n >= study.samples) { setRunning(false); setMessage('Simulación completada. Puedes revisar y guardar el estudio de prueba.'); }
    };
    timer.current = setInterval(tick, 100);
    return () => clearInterval(timer.current);
  }, [running, study]);

  // ----- Helpers de UI ------------------------------------------------------
  function updateSamples(n) { const v = Math.max(min, Math.min(max, Math.round(n))); setSamples(v); setDraft(String(v)); }
  function changeRate(rate) { const v = Math.round(duration * rate); setFs(rate); setSamples(v); setDraft(String(v)); }

  async function start() {
    if (!valid || running || busy) return; setBusy(true); setMessage('Generando señal en Python…');
    try {
      const data = await window.ecgDesktop.backend('simulate', { samples, fs });
      if (data.source !== 'python' || data.samples !== samples || data.fs !== fs || data.raw?.length !== samples || data.filtered?.length !== samples || data.time?.length !== samples)
        throw new Error('Respuesta de Python incompatible');
      const s = { ...data, id: crypto.randomUUID(), patient: { ...patient, name: patient.name.trim() }, patient_id: patientId, date: new Date().toISOString() };
      setDialog(null); setStudy(s); setCount(0); setSaved(false); setMessage('Reproduciendo señal sintética generada por Python…');
      clock.current = performance.now(); setRunning(true);
    } catch (e) { setDialog(null); setMessage(String(e.message || e)); checkBackend(); }
    finally { setBusy(false); }
  }

  async function startBench() {
    if (!valid || busy || running || !confirmed || !port || power !== 'battery' || ![100, 250].includes(fs) || (protocol === 'numeric' && (fs !== 100 || physicalMode !== 'bench')))
      return;
    setBusy(true);
    try {
      const r = await window.ecgDesktop.backend('benchStart', { port, samples, fs, protocol, mode: physicalMode, confirmed_bench: physicalMode === 'bench', confirmed_experimental: physicalMode === 'experimental' });
      setStudy({ id: r.id, patient: { ...patient, name: patient.name.trim() }, patient_id: patientId, date: new Date().toISOString(), mode: physicalMode, state: 'connecting', fs, samples, duration, raw: [], filtered: [], time: [], lead: [] });
      setCount(0); setSaved(false); setRunning(true); setBenchId(r.id); setDialog(null); setMessage('Conectando Arduino…');
    } catch (e) { setPortError(String(e.message || e)); } finally { setBusy(false); }
  }

  function stop() {
    if (benchId) { void window.ecgDesktop.backend('benchStop', { id: benchId }).catch(e => setMessage(String(e.message || e))); setMessage('Deteniendo prueba…'); return; }
    setRunning(false); setMessage('Simulación interrumpida. No se guardará como un estudio completo.');
  }

  // ----- Persistencia --------------------------------------------------------
  async function save() {
    if (!complete || saved || busy || processing) return;
    if (!window.confirm('El estudio y sus datos se guardarán en la base local sin cifrado de la aplicación. Confirma que tienes autorización para conservar estos datos y que el equipo está protegido. ¿Guardar?')) return;
    setBusy(true);
    try {
      const r = await window.ecgDesktop.backend('storageSave', study);
      setStudy(old => ({ ...old, patient_id: r.patient_id })); setSaved(true); setDbStatus('online'); setMessage('Estudio e imagen PNG guardados permanentemente en MongoDB.');
    } catch (e) { setMessage('No se guardó: ' + String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function archive(action) {
    if (busy || running || processing) return;
    if (action === 'restore' && !window.confirm('Se creará una base independiente. No se reemplazará la original. ¿Continuar?')) return;
    setBusy(true);
    setBackupMessage(action === 'create' ? 'Preparando respaldo…' : 'Restaurando copia independiente…');
    try {
      const r = await window.ecgDesktop.backup(action);
      if (r.cancelled) { setBackupMessage('Operación cancelada.'); return; }
      if (action === 'restore') {
        setRestoredDb(r.compatible ? r.database : null);
        setBackupMessage('Restauración creada: ' + r.database + '. ' + r.counts.estudios + ' estudios. ' + (r.compatible ? 'Puedes abrirla en esta sesión.' : 'Datos antiguos conservados; requieren migración antes de abrirlos en el monitor.'));
      } else {
        setBackupMessage('Respaldo creado: ' + r.file + ' · ' + r.counts.estudios + ' estudios.' + (r.compatible ? '' : ' Incluye registros antiguos conservados sin modificar; requieren migración para abrirlos en el monitor.'));
      }
    } catch (e) { setBackupMessage('No se completó: ' + String(e.message || e)); }
    finally { setBusy(false); }
  }

  // ----- Renderizado ----------------------------------------------------------
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">∿</div>
          <div><strong>ECG Analyzer</strong><small>BIOMEDICAL LAB</small></div>
        </div>
        <div className="nav-title">ÁREA DE TRABAJO</div>
        {[['monitor', '⌁', 'Monitor ECG'], ['history', '▤', 'Historial'], ['settings', '⚙', 'Configuración']].map(([key, icon, label]) => (
          <button key={key} className={'nav ' + (tab === key ? 'current' : '')} disabled={running || busy || processing} onClick={() => { if (key === 'history') setSearch(''); setTab(key); }}>
            <span>{icon}</span>{label}
          </button>
        ))}
        <div className="side-note"><span className="dot"/> ECG Analyzer · v1.0.0<br/><small>Uso académico y experimental</small></div>
      </aside>
      {/* El resto del UI se mantiene sin cambios para ahorrar espacio */}
    </div>
  );
}
