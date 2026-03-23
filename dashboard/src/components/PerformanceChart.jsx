import { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';

const CONTENT_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'daily_verse', label: 'Daily Verse' },
  { value: 'marriage_monday', label: 'Marriage Monday' },
  { value: 'faith_friday', label: 'Faith Friday' },
  { value: 'encouragement', label: 'Encouragement' },
  { value: 'carousel', label: 'Carousel' },
  { value: 'christian_quote', label: 'Christian Quote' },
];

export default function PerformanceChart({ data }) {
  const [typeFilter, setTypeFilter] = useState('');

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!typeFilter) return data;
    return data.filter((d) => d.content_type === typeFilter);
  }, [data, typeFilter]);

  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 text-center text-gray-400">
        No performance data available
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
      {/* Filter */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading text-lg text-brand-green">Performance Over Time</h3>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-gold/40"
        >
          {CONTENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={filtered} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: '#888' }}
            tickLine={false}
          />
          <YAxis tick={{ fontSize: 12, fill: '#888' }} tickLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#FFF8F0',
              border: '1px solid #e5ddd0',
              borderRadius: '8px',
              fontSize: '13px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          <Line
            type="monotone"
            dataKey="reach"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Reach"
          />
          <Line
            type="monotone"
            dataKey="engagement"
            stroke="#D4A853"
            strokeWidth={2}
            dot={false}
            name="Engagement"
          />
          <Line
            type="monotone"
            dataKey="likes"
            stroke="#2D4A3E"
            strokeWidth={2}
            dot={false}
            name="Likes"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
