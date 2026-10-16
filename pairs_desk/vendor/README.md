# KLineChart local

`install_klinechart.py` instala **KLineChart 9.8.12** (`dist/umd/klinecharts.min.js`) en esta carpeta y verifica su **SHA-256** contra `klinecharts.sha256` (coincide con el paquete oficial de npm).

- Archivo presente y correcto: se usa.
- Archivo presente pero alterado: error de integridad (código 2); los launchers abortan.
- Archivo ausente: se descarga (unpkg o jsDelivr) y solo se instala si el hash coincide.

Para actualizar la versión: cambiar `VERSION` en `install_klinechart.py`, reemplazar el archivo y regenerar `klinecharts.sha256` con `sha256sum klinecharts.min.js`, comparando antes contra `npm pack klinecharts@<versión>`.
