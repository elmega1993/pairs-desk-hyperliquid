import { defineConfig } from 'vite';
export default defineConfig({ base: '/react/assets/', build: { outDir: '../react_dist', emptyOutDir: true, assetsDir: 'assets' } });
