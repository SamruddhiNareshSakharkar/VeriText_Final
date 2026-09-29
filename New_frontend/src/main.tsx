import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// #region agent log
function dbg(message: string, data: Record<string, unknown>, hypothesisId: string) {
  fetch('http://127.0.0.1:7269/ingest/5765b5d4-be54-401c-a6dd-2cbc0c00d0c0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'7d2f9e'},body:JSON.stringify({sessionId:'7d2f9e',runId:'pre-fix',hypothesisId,location:'main.tsx',message,data,timestamp:Date.now()})}).catch(()=>{});
}
window.addEventListener('error', (e) => {
  dbg('window.error', { msg: String(e.error?.message || e.message || ''), stack: String(e.error?.stack || '').slice(0, 500), href: location.pathname }, 'A');
});
window.addEventListener('unhandledrejection', (e) => {
  dbg('unhandledrejection', { msg: String((e.reason && e.reason.message) || e.reason || ''), href: location.pathname }, 'D');
});
// #endregion

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
