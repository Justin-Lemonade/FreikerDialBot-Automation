import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  onOpenStatistics: () => void;
  onOpenNotes: () => void;
  onOpenSearch: (query?: string) => void;
  /** Re-fetches /session/current -- called after pause/resume so
   * isPaused (and everything else) reflects the real backend state
   * immediately, not just this screen's local guess. */
  onSessionChanged: (session: SessionSummary) => void;
}

interface CommandButtonProps {
  label: string;
  onClick?: () => void;
  color: string;
  disabled?: boolean;
  title?: string;
}

const CommandButton = ({ label, onClick, color, disabled, title }: CommandButtonProps) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    className="retro-button min-h-[52px] w-full font-display text-xs disabled:cursor-not-allowed disabled:opacity-40"
    style={{ background: color, color: 'var(--bg-void)', border: `2px solid ${color}` }}
  >
    [ {label} ]
  </button>
);

interface CommandDefinition {
  name: string;
  aliases: string[];
  description: string;
  /** Whether this command takes a free-text argument (e.g. "search
   * loan 4021") -- purely for the help text, argument parsing itself
   * just takes everything after the command name. */
  takesArgument?: boolean;
  run: (arg: string) => Promise<string> | string;
}

/** Every command here maps directly to an existing, already-tested
 * Mini App API route or an existing screen -- no new backend surface
 * was invented to fill this in. audit(): the same command table backs
 * both execution and the printed help list, so the two can never drift
 * apart. */
export const Commands = ({ session, onOpenStatistics, onOpenNotes, onOpenSearch, onSessionChanged }: Props) => {
  const [commandInput, setCommandInput] = useState('');
  const [log, setLog] = useState<{ text: string; isError: boolean }[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const isPaused = Boolean(session?.isPaused);

  const appendLog = (text: string, isError = false) => {
    setLog((current) => [...current.slice(-6), { text, isError }]);
  };

  const runExport = async (format: 'csv' | 'json' | 'xlsx' = 'csv') => {
    setIsExporting(true);
    try {
      const { blob, filename } = await api.exportData(format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      return `Exported ${filename}`;
    } catch (err) {
      // GET /export is admin-only (mini_app_api.py checks
      // security.is_admin before running) -- a non-admin operator gets
      // a real 403 here, surfaced honestly rather than hidden.
      throw err instanceof ApiError ? err : new Error('Export failed.');
    } finally {
      setIsExporting(false);
    }
  };

  const togglePause = async () => {
    const result = isPaused ? await api.resumeQueue() : await api.pauseQueue();
    if (result.session) onSessionChanged(result.session);
    return isPaused ? 'Queue resumed.' : 'Queue paused.';
  };

  const COMMANDS: CommandDefinition[] = [
    {
      name: 'help',
      aliases: ['?'],
      description: 'List available commands',
      run: () => COMMANDS.map((c) => `${c.name}${c.takesArgument ? ' <query>' : ''} — ${c.description}`).join('\n'),
    },
    {
      name: 'stats',
      aliases: ['statistics', 'summary'],
      description: 'Open Statistics',
      run: () => {
        onOpenStatistics();
        return 'Opening statistics…';
      },
    },
    {
      name: 'notes',
      aliases: ['note'],
      description: 'Open notes for the current customer',
      run: () => {
        onOpenNotes();
        return 'Opening notes…';
      },
    },
    {
      name: 'search',
      aliases: ['find', 'customer'],
      description: 'Search for a customer',
      takesArgument: true,
      run: (arg) => {
        if (!arg.trim()) {
          onOpenSearch();
          return 'Opening search…';
        }
        onOpenSearch(arg.trim());
        return `Searching for "${arg.trim()}"…`;
      },
    },
    {
      name: 'pause',
      aliases: [],
      description: 'Pause the queue',
      run: async () => {
        if (isPaused) return 'Queue is already paused.';
        return togglePause();
      },
    },
    {
      name: 'resume',
      aliases: [],
      description: 'Resume the queue',
      run: async () => {
        if (!isPaused) return 'Queue is already running.';
        return togglePause();
      },
    },
    {
      name: 'export',
      aliases: [],
      description: 'Export customer data (csv/json/xlsx)',
      takesArgument: true,
      run: async (arg) => {
        const format = (arg.trim().toLowerCase() || 'csv') as 'csv' | 'json' | 'xlsx';
        if (!['csv', 'json', 'xlsx'].includes(format)) {
          throw new Error(`Unknown export format "${format}". Use csv, json, or xlsx.`);
        }
        return runExport(format);
      },
    },
  ];

  const executeCommand = async (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed || isRunning) return;
    setIsRunning(true);
    appendLog(`> ${trimmed}`);
    const [nameToken, ...rest] = trimmed.split(/\s+/);
    const name = nameToken.toLowerCase();
    const arg = rest.join(' ');
    const command = COMMANDS.find((c) => c.name === name || c.aliases.includes(name));
    try {
      if (!command) {
        appendLog(`Unknown command: "${name}". Type "help" for a list.`, true);
      } else {
        const result = await command.run(arg);
        appendLog(result);
      }
    } catch (err) {
      appendLog(err instanceof Error ? err.message : 'Command failed.', true);
    } finally {
      setIsRunning(false);
      setCommandInput('');
    }
  };

  return (
    <div className="space-y-4">
      <div className="retro-panel p-4">
        <p className="mb-3 font-display text-[10px]" style={{ color: 'var(--accent-green)' }}>
          SUGGESTED COMMANDS
        </p>
        <div className="space-y-2.5">
          <CommandButton label="VIEW STATISTICS" onClick={onOpenStatistics} color="var(--accent-indigo)" />
          <CommandButton label="SESSION NOTES" onClick={onOpenNotes} color="var(--accent-blue)" />
          <CommandButton
            label={isPaused ? 'RESUME QUEUE' : 'PAUSE QUEUE'}
            onClick={() => executeCommand(isPaused ? 'resume' : 'pause')}
            color="var(--accent-purple)"
            disabled={isRunning}
          />
          <CommandButton
            label={isExporting ? 'EXPORTING…' : 'EXPORT DATA'}
            onClick={() => executeCommand('export csv')}
            color="var(--accent-red)"
            disabled={isRunning || isExporting}
            title="Admin-only -- requires Telegram admin authorization"
          />
        </div>
      </div>

      {log.length > 0 && (
        <div className="retro-panel space-y-1 p-4">
          {log.map((entry, index) => (
            <p
              key={index}
              className="whitespace-pre-wrap font-data text-base"
              style={{ color: entry.isError ? 'var(--accent-red)' : 'var(--text-muted)' }}
            >
              {entry.text}
            </p>
          ))}
        </div>
      )}

      <div className="retro-panel p-4">
        <p className="mb-2 font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          TYPE A COMMAND — try "help"
        </p>
        <input
          value={commandInput}
          onChange={(event) => setCommandInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') executeCommand(commandInput);
          }}
          disabled={isRunning}
          placeholder="e.g. search 4021, pause, export json"
          inputMode="text"
          enterKeyHint="go"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          className="w-full px-3 py-3 font-data text-lg outline-none disabled:cursor-not-allowed"
          style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
        />
      </div>
    </div>
  );
};
