export const Settings = () => {
  return (
    <div className="space-y-4">
      <div className="rounded-[32px] border border-white/10 bg-slate-900/80 p-5">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">Mini App</p>
        <h2 className="mt-2 text-2xl font-semibold">Settings</h2>
        <p className="mt-2 text-sm text-slate-400">Theme-aware, full-screen, and touch optimized for calling sessions.</p>
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-800/70 px-3 py-3">
          <div>
            <p className="font-semibold">Telegram Theme</p>
            <p className="text-sm text-slate-400">Uses WebApp theme colors</p>
          </div>
          <div className="text-emerald-300">On</div>
        </div>
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-800/70 px-3 py-3">
          <div>
            <p className="font-semibold">Haptics</p>
            <p className="text-sm text-slate-400">Vibrations for key actions</p>
          </div>
          <div className="text-emerald-300">Enabled</div>
        </div>
      </div>
    </div>
  );
};
