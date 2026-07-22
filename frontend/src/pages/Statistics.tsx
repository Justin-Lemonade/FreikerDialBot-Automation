import { StatisticsCard } from '../components/StatisticsCard';
import type { SessionSummary, StatisticsData } from '../types';

interface Props {
  session: SessionSummary | null;
}

const stats: StatisticsData = {
  todaysCalls: 24,
  answered: 16,
  didntAnswer: 5,
  wrongNumber: 3,
  averageCallTime: '2m 11s',
  successRate: '67%',
  lifetimeCalls: 482,
  sessions: 31,
  customersContacted: 271,
  bestDay: 'Jun 28',
};

export const Statistics = (_props: Props) => {
  return (
    <div className="space-y-4">
      <div className="rounded-[32px] border border-white/10 bg-gradient-to-b from-slate-900 to-slate-800 p-5 shadow-2xl">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">Today's calls</p>
        <h2 className="mt-2 text-2xl font-semibold">Performance snapshot</h2>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <StatisticsCard title="Answered" value={`${stats.answered}`} helper="Successful contacts" />
        <StatisticsCard title="Didn't Answer" value={`${stats.didntAnswer}`} helper="No answer" />
        <StatisticsCard title="Wrong Number" value={`${stats.wrongNumber}`} helper="Bad contact" />
        <StatisticsCard title="Average Call Time" value={stats.averageCallTime} helper="Current average" />
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="text-sm text-slate-400">Success rate</p>
        <p className="mt-2 text-3xl font-semibold">{stats.successRate}</p>
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="text-sm text-slate-400">Lifetime statistics</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <StatisticsCard title="Calls" value={`${stats.lifetimeCalls}`} helper="Total handled" />
          <StatisticsCard title="Sessions" value={`${stats.sessions}`} helper="Completed" />
          <StatisticsCard title="Customers Contacted" value={`${stats.customersContacted}`} helper="Successful outcomes" />
          <StatisticsCard title="Best Day" value={stats.bestDay} helper="Highest volume" />
        </div>
      </div>
    </div>
  );
};
