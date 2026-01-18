import { defineConfig } from 'vite';

export default defineConfig({
  root: 'src',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    target: 'es2022', // Support top-level await
    rollupOptions: {
      input: {
        main: 'src/index.html',
        agents: 'src/agents.html',
        palette: 'src/command-palette.html',
        login: 'src/login.html',
        onboarding: 'src/onboarding.html',
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
});
