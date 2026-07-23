import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * host: true binds to 0.0.0.0 so start_mini_app.py's ngrok tunnel (which
 * points at this dev server) can actually reach it -- `npx vite` alone
 * only binds localhost, which ngrok can't tunnel to from outside the
 * container/VM.
 *
 * No backend proxy here: the frontend talks to mini_app_api.py directly
 * via an absolute URL (VITE_API_BASE_URL, see src/api/client.ts) since
 * the two run as separate processes on separate ports (see
 * start_mini_app.py) rather than one process Vite could proxy to.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
});
