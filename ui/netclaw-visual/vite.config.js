import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        timeout: 300000,
        configure: (proxy) => {
          proxy.on('proxyReq', (_proxyReq, _req, res) => {
            // Keep socket alive for 5 minutes (gateway may run many tools)
            res.setTimeout(300000);
          });
        },
      },
      '/ws': {
        target: 'ws://localhost:3001',
        ws: true,
      },
    },
  },
});
