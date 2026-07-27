interface Props {
  title: string;
  value: string;
  helper: string;
}

export const StatisticsCard = ({ title, value, helper }: Props) => {
  return (
    <div className="retro-panel p-4">
      <p className="font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
        {title}
      </p>
      <p className="mt-2 font-data text-2xl" style={{ color: 'var(--accent-green)' }}>
        {value}
      </p>
      <p className="mt-1 font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        {helper}
      </p>
    </div>
  );
};
