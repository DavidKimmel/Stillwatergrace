import { useQuery } from '@tanstack/react-query';
import { fetchCompetitors } from '../lib/api';
import { Users, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function CompetitorsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['competitors'],
    queryFn: fetchCompetitors,
  });

  const competitors = data || [];

  return (
    <div>
      <h2 className="text-2xl font-heading font-bold mb-6">Competitor Watch</h2>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card h-20 animate-pulse bg-gray-100" />
          ))}
        </div>
      ) : competitors.length === 0 ? (
        <div className="card text-center text-gray-400 py-12">
          <Users size={40} className="mx-auto mb-3 opacity-30" />
          <p>No competitor data yet.</p>
          <p className="text-sm mt-1">Data will appear after the weekly competitor scrape runs.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-3 font-medium">Handle</th>
                <th className="pb-3 font-medium text-right">Followers</th>
                <th className="pb-3 font-medium text-right">Change</th>
                <th className="pb-3 font-medium text-right">Engagement</th>
                <th className="pb-3 font-medium text-right">Posts/Week</th>
                <th className="pb-3 font-medium text-right">Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {competitors.map((c) => (
                <tr key={c.handle} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3">
                    <a
                      href={`https://instagram.com/${c.handle}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-green hover:text-brand-gold font-medium"
                    >
                      @{c.handle}
                    </a>
                  </td>
                  <td className="py-3 text-right font-medium">
                    {(c.followers || 0).toLocaleString()}
                  </td>
                  <td className="py-3 text-right">
                    <DeltaBadge value={c.follower_delta} />
                  </td>
                  <td className="py-3 text-right">
                    {c.avg_engagement_rate
                      ? `${(c.avg_engagement_rate * 100).toFixed(2)}%`
                      : '—'}
                  </td>
                  <td className="py-3 text-right">
                    {c.posting_frequency_per_week
                      ? c.posting_frequency_per_week.toFixed(1)
                      : '—'}
                  </td>
                  <td className="py-3 text-right text-gray-400 text-xs">
                    {c.captured_at
                      ? new Date(c.captured_at).toLocaleDateString()
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Benchmarking Card */}
      <div className="card mt-6">
        <h3 className="font-semibold mb-3">Benchmarking Notes</h3>
        <ul className="text-sm text-gray-600 space-y-2">
          <li>Prioritize <strong>saves and shares</strong> over likes — these signal content people want to return to.</li>
          <li>Engagement rate above <strong>3%</strong> is strong for faith niche. Above <strong>5%</strong> is excellent.</li>
          <li>Watch competitor posting frequency. If top pages post 2-3x/day, match that cadence.</li>
          <li>Note which content types competitors lean on most — carousel, reels, or static posts?</li>
        </ul>
      </div>
    </div>
  );
}

function DeltaBadge({ value }) {
  if (!value || value === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-gray-400 text-xs">
        <Minus size={12} /> 0
      </span>
    );
  }

  if (value > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-green-600 text-xs font-medium">
        <TrendingUp size={12} /> +{value.toLocaleString()}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 text-red-600 text-xs font-medium">
      <TrendingDown size={12} /> {value.toLocaleString()}
    </span>
  );
}
