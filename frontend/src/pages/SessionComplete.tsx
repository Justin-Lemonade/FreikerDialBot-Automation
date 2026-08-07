import { useState } from 'react';
import { api, ApiError } from '../api/client';
import { downloadBlob } from '../lib/download';
import type { SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  onRetry: () => void;
  onHome: () => void;
}

export const SessionComplete = ({ session, onRetry, onHome }: Props) => {
  const contacted = session?.progress?.contacted;
  const didNotAnswer = session?.progress?.didNotAnswer;
  const hasBreakdown = contacted !== undefined && didNotAnswer !== undefined;
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      // GET /export is admin-only (mini_app_api.py checks
      // security.is_admin) -- a non-admin operator sees a real error
      // here instead of the button silently doing nothing, which is
      // what it did before this had an onClick at all.
      const { blob, filename } = await api.exportData('csv');
      downloadBlob(blob, filename);
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : 'Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="retro-card p-6 text-center" style={{ borderColor: 'var(--accent-green-strong)' }}>
        <p className="font-display text-[10px]" style={{ color: 'var(--accent-green)' }}>
          SESSION COMPLETE
        </p>
        <h2 className="mt-3 font-data text-3xl" style={{ color: 'var(--text-primary)' }}>
          {session?.customerCount ?? 0} customers processed
        </h2>
        {hasBreakdown && (
          <p className="mt-2 font-data text-lg" style={{ color: 'var(--text-muted)' }}>
            {contacted} contacted • {didNotAnswer} didn&apos;t answer
          </p>
        )}
      </div>

      {exportError && (
        <div className="p-3 text-center font-data text-base" style={{ border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }}>
          {exportError}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onRetry}
          className="retro-button min-h-[56px] font-display text-[10px]"
          style={{ border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
        >
          RETRY NO-ANSWER
        </button>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="retro-button min-h-[56px] font-display text-[10px] disabled:cursor-not-allowed disabled:opacity-50"
          style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
        >
          {isExporting ? 'EXPORTING…' : 'EXPORT'}
        </button>
      </div>
      <button
        onClick={onHome}
        className="retro-button min-h-[56px] w-full font-display text-sm"
        style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
      >
        RETURN HOME
      </button>
    </div>
  );
};
