import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchAnalyticsOverview,
  fetchTopPosts,
  fetchContentTypePerformance,
  fetchPostingHistory,
  fetchPlatformBreakdown,
} from '../lib/api';
import MetricCard from '../components/MetricCard';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Heart, Bookmark, Share2, Eye, TrendingUp } from 'lucide-react';
import { format } from 'date-fns';

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

  const { data: postingHistory } = useQuery({
    queryKey: ['posting-history', days],
    queryFn: () => fetchPostingHistory(days),
  });

  const { data: platformBreakdown } = useQuery({
    queryKey: ['platform-breakdown', days],
    queryFn: () => fetchPlatformBreakdown(days),
  });

  const platformData = platformBreakdown
    ? Object.entries(platformBreakdown).map(([name, stats]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        success: stats.success || 0,
        failed: stats.failed || 0,
      }))
    : [];

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

      {/* Platform Breakdown */}
      {platformData.length > 0 && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Posts by Platform</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={platformData} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 12 }} width={80} />
              <Tooltip />
              <Bar dataKey="success" fill="#2D4A3E" name="Success" stackId="a" radius={[0, 4, 4, 0]} />
              <Bar dataKey="failed" fill="#ef4444" name="Failed" stackId="a" radius={[0, 4, 4, 0]} />
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

      {/* Posting History */}
      <div className="card mt-6">
        <h3 className="font-semibold mb-4">Recent Posting Activity</h3>
        {postingHistory && postingHistory.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2 font-medium">Content</th>
                  <th className="pb-2 font-medium">Platform</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Posted</th>
                  <th className="pb-2 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {postingHistory.map((log) => (
                  <tr key={log.id} className="border-b border-gray-50">
                    <td className="py-2">#{log.content_id}</td>
                    <td className="py-2 capitalize">{log.platform}</td>
                    <td className="py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        log.status === 'success' ? 'text-green-600 bg-green-50' :
                        log.status === 'failed' ? 'text-red-600 bg-red-50' :
                        'text-gray-400 bg-gray-50'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="py-2 text-xs text-gray-500">
                      {log.posted_at ? format(new Date(log.posted_at), 'MMM d, h:mm a') : '--'}
                    </td>
                    <td className="py-2 text-xs text-red-500 max-w-[200px] truncate">
                      {log.error_message || ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-400 text-center py-4">No posting activity yet.</p>
        )}
      </div>
    </div>
  );
}
