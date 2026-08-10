import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Kept separate from vite.config.ts (the production build config) so
 * test-only settings (environment, globals) can never accidentally
 * affect `npm run build` or `npm run dev`.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: false,
  },
});
