import React from 'react';
import {createRoot} from 'react-dom/client';
import {App} from './App';

// Load the locally vendored chart engine before mounting React. This is an
// intentionally non-module UMD asset served by FastAPI, not a Vite import.
function loadChartEngine(): Promise<void> {
  if (window.klinecharts) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/vendor/klinecharts.min.js';
    script.onload = () => window.klinecharts ? resolve() : reject(new Error('KLineCharts no inicializó'));
    script.onerror = () => reject(new Error('No se pudo cargar /vendor/klinecharts.min.js'));
    document.head.appendChild(script);
  });
}

const root = createRoot(document.getElementById('root')!);
loadChartEngine().then(() => {
  root.render(<React.StrictMode><App/></React.StrictMode>);
}).catch(error => {
  root.render(<main style={{padding:24,color:'#ff9ba9',background:'#101827',minHeight:'100vh'}}>
    <h2>No se pudo iniciar el gráfico</h2><p>{String(error)}</p>
    <p>Verificá que el archivo local de KLineCharts exista y que el servidor responda en /vendor/klinecharts.min.js.</p>
  </main>);
});
