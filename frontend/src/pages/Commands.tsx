interface Props {
  onOpenStatistics: () => void;
  onOpenNotes: () => void;
}

/**
 * Secondary-actions page. Statistics and Notes previously lived as
 * bottom-nav buttons; the requested nav shell is Home/Commands/Search/
 * Settings, so they moved here rather than losing a top-level slot.
 * More actions can be added as rows here as they're built (e.g. queue
 * pause/resume, blacklist management) without needing new nav slots.
 */
export const Commands = ({ onOpenStatistics, onOpenNotes }: Props) => {
  return (
    <div className="space-y-3">
      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="mb-3 text-sm font-semibold text-slate-300">Commands</p>
        <div className="space-y-2">
          <button
            onClick={onOpenStatistics}
            className="flex min-h-[56px] w-full items-center justify-between rounded-2xl border border-white/10 bg-slate-800/70 px-4 active:scale-[0.98]"
          >
            <span className="font-semibold">📊 Statistics</span>
            <span className="text-slate-400">›</span>
          </button>
          <button
            onClick={onOpenNotes}
            className="flex min-h-[56px] w-full items-center justify-between rounded-2xl border border-white/10 bg-slate-800/70 px-4 active:scale-[0.98]"
          >
            <span className="font-semibold">📝 Session Notes</span>
            <span className="text-slate-400">›</span>
          </button>
        </div>
      </div>
    </div>
  );
};
