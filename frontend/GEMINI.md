# Frontend Project Instructions

> **See `AGENTS.md` for canonical architecture, source-of-truth rules, and
> validation commands.** This file keeps only Gemini-specific workflow
> notes to avoid duplicating content that now lives in `AGENTS.md`.

This directory contains the React/TypeScript frontend application for the
FreikerDialBot Automation project (Telegram Mini App).

## Technology Stack

- React 19
- TypeScript 6.x
- Vite 8.x (build tool)
- Tailwind CSS 3.x (styling)
- oxlint (linting)

## Available Scripts

- `npm install`: Install dependencies. Use `npm ci` for read-only/clean
  installs (respects lockfile exactly).
- `npm run dev`: Start the Vite development server on port 5173.
- `npm run build`: Typecheck + production build.
- `npm run lint`: Run oxlint.
- `npm run preview`: Preview production build locally.

## Project Structure

- `src/` — Main application source code.
- `src/pages/` — Page-level components (Home, CustomerDetail, Search,
  Settings, Statistics, SessionComplete, Commands).
- `src/components/` — Reusable UI components (CallButton, CustomerCard,
  OutcomeButtons, ProgressHeader, SettingsDrawer, StatisticsCard).
- `src/hooks/` — Custom React hooks (useCallTimer, useCustomer, useSession,
  useTelegram).
- `src/api/` — API client and related logic.

## Development Guidelines

- Mobile-first layout with large touch targets (Telegram Mini App target).
- Use TypeScript strict mode.
- Connect to real backend endpoints — no hardcoded/placeholder customer
  data in production components.
- Run lint and typecheck before committing.