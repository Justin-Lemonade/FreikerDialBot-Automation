import { useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import { readFileAsBase64, readFileAsText } from '../lib/fileReading';
import type { ImportResult } from '../types';

interface Props {
  onBack: () => void;
  /** Called after a successful import that created a session, so the
   * caller can offer "Continue Session" for it -- App.tsx already
   * polls /session/current on an interval, but this lets the operator
   * jump straight into calling instead of waiting for the next poll. */
  onImported: () => void;
}

type Status = 'idle' | 'reading' | 'importing' | 'done' | 'error';

const SUPPORTED_EXTENSIONS = ['.json', '.xlsx'];

/**
 * Real Mini App import screen (GAP-001) -- previously importing was
 * Telegram-only. Runs through the same POST /import backed by the
 * shared Importer pipeline (see mini_app_api.MiniAppService.import_data
 * and importer.py), not a separate/fake implementation. Supports the
 * same two structured formats the Telegram bot's file handlers do
 * (.json, .xlsx); free-text/screenshot AI-parsed import stays
 * Telegram-only for now -- that path needs a chat-style back-and-forth
 * this screen doesn't have yet, not a technical limitation of /import
 * itself (format="json" already runs through the same import_text()
 * the AI path also uses, so a future pass could add it here directly).
 */
export const Upload = ({ onBack, onImported }: Props) => {
  const [status, setStatus] = useState<Status>('idle');
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setFileName(file.name);
    setResult(null);
    setError(null);

    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!SUPPORTED_EXTENSIONS.includes(extension)) {
      setStatus('error');
      setError(`Unsupported file type "${extension}". Please choose a .json or .xlsx file.`);
      return;
    }

    setStatus('reading');
    try {
      const format = extension === '.xlsx' ? 'xlsx' : 'json';
      const data = format === 'xlsx' ? await readFileAsBase64(file) : await readFileAsText(file);

      setStatus('importing');
      const response = await api.importData(format, data);
      setResult(response);
      if (response.ok) {
        setStatus('done');
        onImported();
      } else {
        setStatus('error');
        setError(response.error || 'Import failed.');
      }
    } catch (err) {
      setStatus('error');
      setError(err instanceof ApiError ? err.message : 'Could not read or import that file.');
    }
  };

  const isBusy = status === 'reading' || status === 'importing';

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="retro-button min-h-[44px] px-4 font-display text-[10px]"
        style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
      >
        ← BACK
      </button>

      <div className="retro-panel p-4">
        <p className="mb-2 font-display text-[10px]" style={{ color: 'var(--accent-green)' }}>
          UPLOAD CONTACTS
        </p>
        <p className="mb-4 font-data text-base" style={{ color: 'var(--text-muted)' }}>
          Choose a .json or .xlsx file exported from your CRM. Each row needs at least a loan number.
        </p>

        <input
          ref={inputRef}
          type="file"
          accept=".json,.xlsx"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) handleFile(file);
            event.target.value = '';
          }}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={isBusy}
          className="retro-button min-h-[56px] w-full font-display text-xs disabled:cursor-not-allowed disabled:opacity-60"
          style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
        >
          {status === 'reading' ? 'READING FILE…' : status === 'importing' ? 'IMPORTING…' : 'CHOOSE FILE'}
        </button>

        {fileName && (
          <p className="mt-2 truncate font-data text-sm" style={{ color: 'var(--text-dim)' }}>
            {fileName}
          </p>
        )}
      </div>

      {status === 'error' && error && (
        <div className="p-4 text-center font-data text-lg" style={{ border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      {status === 'done' && result?.ok && (
        <div className="retro-panel space-y-1 p-4">
          <p className="font-display text-[10px]" style={{ color: 'var(--accent-green)' }}>
            IMPORT COMPLETE
          </p>
          <p className="font-data text-2xl" style={{ color: 'var(--text-primary)' }}>
            {result.importedCount} customer{result.importedCount === 1 ? '' : 's'} imported
          </p>
          {!!result.flaggedCount && (
            <p className="font-data text-base" style={{ color: 'var(--accent-amber)' }}>
              {result.flaggedCount} flagged for review (missing or invalid data)
            </p>
          )}
          {(result.verificationWarnings ?? []).map((warning, index) => (
            <p key={index} className="font-data text-sm" style={{ color: 'var(--text-muted)' }}>
              {warning}
            </p>
          ))}
          {(result.errors ?? []).map((message, index) => (
            <p key={index} className="font-data text-sm" style={{ color: 'var(--accent-red)' }}>
              {message}
            </p>
          ))}
          <button
            onClick={onBack}
            className="retro-button mt-3 min-h-[48px] w-full font-display text-xs"
            style={{ background: 'var(--accent-blue)', color: 'var(--accent-blue-text)', border: '2px solid var(--accent-blue)' }}
          >
            DONE
          </button>
        </div>
      )}
    </div>
  );
};
