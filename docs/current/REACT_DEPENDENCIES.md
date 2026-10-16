# React: instalación reproducible

`react_frontend/package-lock.json` está incluido. En una carpeta sin `node_modules`, el launcher ejecuta `npm ci`; si algún día falta el lockfile, `npm install` lo regenera y conviene conservarlo.

El motor gráfico es el archivo local `pairs_desk/vendor/klinecharts.min.js` (KLineCharts 9.8.12), servido por FastAPI desde `/vendor/klinecharts.min.js` y cargado antes de montar React. Vite no intenta compilar este script UMD.

Su SHA-256 está fijado en `pairs_desk/vendor/klinecharts.sha256` y coincide con el paquete oficial `klinecharts@9.8.12` de npm. `install_klinechart.py` lo verifica en cada arranque: si el archivo no coincide, el launcher aborta (código 2); si falta y hay red, lo descarga y solo lo instala si el hash coincide.
