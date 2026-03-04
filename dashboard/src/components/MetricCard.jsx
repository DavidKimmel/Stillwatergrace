const COLOR_MAP = {
  yellow: 'bg-yellow-50 text-yellow-700',
  blue: 'bg-blue-50 text-blue-700',
  green: 'bg-green-50 text-green-700',
  gold: 'bg-amber-50 text-amber-700',
  red: 'bg-red-50 text-red-700',
};

export default function MetricCard({ icon: Icon, label, value, sublabel, color = 'blue' }) {
  return (
    <div className={`card flex items-center gap-4 ${COLOR_MAP[color] || ''}`}>
      {Icon && (
        <div className="p-2 rounded-lg bg-white/60">
          <Icon size={20} />
        </div>
      )}
      <div>
        <div className="text-2xl font-bold font-heading">{value}</div>
        <div className="text-xs opacity-70">{label}</div>
        {sublabel && <div className="text-xs text-red-500 mt-0.5">{sublabel}</div>}
      </div>
    </div>
  );
}
