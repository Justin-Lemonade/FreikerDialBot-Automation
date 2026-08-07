import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Kept separate from vite.config.ts (the production build config) so
 * test-only settings (environment, globals) can never accidentally
 * affect `npm run build` or `npm run dev`. Covers pure logic that has
 * no backend dependency -- see FreikerDialBot_UI_UX_Development_Log.md's
 * "no frontend test runner" gap and the specific functions it named
 * (lib/download.ts, Search's match-highlighting logic, Commands'
 * command parser).
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: false,
  },
});
