import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchAnalyticsOverview,
  fetchTopPosts,
  fetchContentTypePerformance,
} from '../lib/api';
import MetricCard from '../components/MetricCard';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { Heart, Bookmark, Share2, Eye, TrendingUp } from 'lucide-react';

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);

  const { data: overview } = useQuery({
    queryKey: ['analytics-overview', days],
    queryFn: () => fetchAnalyticsOverview(days),
  });

  const { data: topPosts } = useQuery({
    queryKey: ['top-posts', days],
    queryFn: () => fetchTopPosts(days, 'saves', 10),
  });

  const { data: typePerf } = useQuery({
    queryKey: ['type-performance', days],
    queryFn: () => fetchContentTypePerformance(days),
  });

  const o = overview || {};

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-heading font-bold">Analytics</h2>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="border rounded-lg px-3 py-1.5 text-sm bg-white"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={60}>Last 60 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <MetricCard icon={Eye} label="Total Reach" value={(o.total_reach || 0).toLocaleString()} color="blue" />
        <MetricCard icon={Heart} label="Likes" value={(o.total_likes || 0).toLocaleString()} color="red" />
        <MetricCard icon={Bookmark} label="Saves" value={(o.total_saves || 0).toLocaleString()} color="gold" />
        <MetricCard icon={Share2} label="Shares" value={(o.total_shares || 0).toLocaleString()} color="green" />
        <MetricCard icon={TrendingUp} label="Avg Engagement" value={`${((o.avg_engagement_rate || 0) * 100).toFixed(2)}%`} color="yellow" />
      </div>

      {/* Content Type Performance Chart */}
      {typePerf && typePerf.length > 0 && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Performance by Content Type</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={typePerf.map((t) => ({
              ...t,
              name: (t.content_type || '').replace(/_/g, ' '),
            }))}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-20} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="avg_saves" fill="#D4A853" name="Avg Saves" radius={[4, 4, 0, 0]} />
              <Bar dataKey="avg_shares" fill="#2D4A3E" name="Avg Shares" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Posts Table */}
      <div className="card">
        <h3 className="font-semibold mb-4">Top Posts (by Saves)</h3>
        {topPosts && topPosts.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2 font-medium">#</th>
                  <th className="pb-2 font-medium">Content</th>
                  <th className="pb-2 font-medium text-right">Saves</th>
                  <th className="pb-2 font-medium text-right">Shares</th>
                  <th className="pb-2 font-medium text-right">Reach</th>
                  <th className="pb-2 font-medium text-right">Engagement</th>
                </tr>
              </thead>
              <tbody>
                {topPosts.map((post, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="py-2 text-gray-400">{i + 1}</td>
                    <td className="py-2">#{post.content_id}</td>
                    <td className="py-2 text-right font-medium text-brand-gold">{post.saves}</td>
                    <td className="py-2 text-right">{post.shares}</td>
                    <td className="py-2 text-right">{(post.reach || 0).toLocaleString()}</td>
                    <td className="py-2 text-right">
                      {((post.engagement_rate || 0) * 100).toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-400 text-center py-8">
            No analytics data yet. Data will appear after posts are published.
          </p>
        )}
      </div>
    </div>
  );
}
