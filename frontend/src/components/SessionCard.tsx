interface Props {
  title: string;
  value: string;
  description: string;
}

export const SessionCard = ({ title, value, description }: Props) => {
  return (
    <div className="rounded-[24px] border border-white/10 bg-slate-900/70 p-4">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-sm text-slate-400">{description}</p>
    </div>
  );
};
