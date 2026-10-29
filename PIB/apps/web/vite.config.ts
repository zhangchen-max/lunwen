import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  publicDir: path.resolve(__dirname, '../../mocks'),
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8780',
        changeOrigin: true,
      },
    },
  },
});
