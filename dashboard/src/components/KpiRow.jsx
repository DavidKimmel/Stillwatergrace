import { TrendingUp, TrendingDown } from 'lucide-react';

const METRICS = [
  { key: 'reach', label: 'Total Reach' },
  { key: 'engagement_rate', label: 'Engagement Rate', format: 'percent' },
  { key: 'likes', label: 'Total Likes' },
  { key: 'saves', label: 'Total Saves' },
  { key: 'shares', label: 'Total Shares' },
];

function formatValue(value, format) {
  if (format === 'percent') {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (typeof value === 'number' && value >= 1000) {
    return value.toLocaleString();
  }
  return value ?? '--';
}

function DeltaBadge({ delta }) {
  if (delta == null || delta === 0) return null;

  const isPositive = delta > 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const colorClass = isPositive
    ? 'text-emerald-600 bg-emerald-50'
    : 'text-red-600 bg-red-50';

  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium px-1.5 py-0.5 rounded-full ${colorClass}`}>
      <Icon size={12} />
      {Math.abs(delta).toFixed(1)}%
    </span>
  );
}

export default function KpiRow({ data }) {
  if (!data) return null;

  const deltas = data.deltas || {};

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      {METRICS.map(({ key, label, format }) => (
        <div
          key={key}
          className="bg-white rounded-xl p-4 shadow-sm border border-gray-100"
        >
          <p className="text-xs text-gray-500 mb-1">{label}</p>
          <p className="text-2xl font-heading text-brand-green font-bold">
            {formatValue(data[key], format)}
          </p>
          <DeltaBadge delta={deltas[key]} />
        </div>
      ))}
    </div>
  );
}
