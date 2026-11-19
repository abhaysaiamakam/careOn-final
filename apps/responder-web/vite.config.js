import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@careon/design-system': path.resolve(__dirname, '../../packages/design-system'),
      '@careon/contracts': path.resolve(__dirname, '../../packages/contracts'),
      '@careon/api-client': path.resolve(__dirname, '../../packages/api-client'),
      '@careon/auth': path.resolve(__dirname, '../../packages/auth'),
    },
  },
  server: {
    port: 3004,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3004,
    host: '0.0.0.0',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
});
