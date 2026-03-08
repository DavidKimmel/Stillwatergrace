import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchInsightsRecommendations,
  fetchInsightsContentType,
  fetchInsightsFormat,
  fetchInsightsTime,
  fetchInsightsCompetitors,
} from '../lib/api';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { TrendingUp, Users, Layers, ChevronDown, ChevronUp } from 'lucide-react';
import { format } from 'date-fns';

const SOURCE_ICONS = {
  performance: TrendingUp,
  competitor: Users,
  both: Layers,
};

const CONFIDENCE_STYLES = {
  high: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-gray-100 text-gray-500',
};

const FORMAT_COLORS = {
  VIDEO: '#D4A853',
  IMAGE: '#2D4A3E',
  CAROUSEL_ALBUM: '#6B8F7E',
};

export default function InsightsPage() {
  const [days, setDays] = useState(30);

  const { data: recommendations } = useQuery({
    queryKey: ['insights-recommendations', days],
    queryFn: () => fetchInsightsRecommendations(days),
  });

  const { data: contentType } = useQuery({
    queryKey: ['insights-content-type', days],
    queryFn: () => fetchInsightsContentType(days),
  });

  const { data: formatData } = useQuery({
    queryKey: ['insights-format', days],
    queryFn: () => fetchInsightsFormat(days),
  });

  const { data: timeData } = useQuery({
    queryKey: ['insights-time', days],
    queryFn: () => fetchInsightsTime(days),
  });

  const { data: competitors } = useQuery({
    queryKey: ['insights-competitors', days],
    queryFn: () => fetchInsightsCompetitors(days),
  });

  const daysSelector = (
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
  );

  const sortedContentType = contentType
    ? [...contentType].sort((a, b) => (b.avg_engagement || 0) - (a.avg_engagement || 0))
    : [];

  const sortedFormat = formatData
    ? [...formatData].sort((a, b) => (b.avg_reach || 0) - (a.avg_reach || 0))
    : [];

  const morning = timeData?.find((t) => t.slot === 'morning') || {};
  const noon = timeData?.find((t) => t.slot === 'noon') || {};
  const morningEng = morning.avg_engagement || 0;
  const noonEng = noon.avg_engagement || 0;
  const morningWins = morningEng >= noonEng;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-heading font-bold">Insights</h2>
        {daysSelector}
      </div>

      {/* Section 1: Recommendations */}
      <div className="mb-8">
        <h3 className="font-semibold text-lg mb-4">Recommendations</h3>
        {recommendations && recommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.map((rec, i) => {
              const SourceIcon = SOURCE_ICONS[rec.source] || TrendingUp;
              return (
                <div key={i} className="card flex flex-col gap-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <SourceIcon size={18} className="text-brand-green shrink-0" />
                      <span className="font-bold text-base">{rec.title}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
                      CONFIDENCE_STYLES[rec.confidence] || CONFIDENCE_STYLES.low
                    }`}>
                      {rec.confidence}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">{rec.why}</p>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="card text-center text-gray-400 py-8">
            <p>No recommendations yet. Data will appear after more posts are published.</p>
          </div>
        )}
      </div>

      {/* Section 2: Performance Breakdown */}
      <div className="mb-8">
        <h3 className="font-semibold text-lg mb-4">Performance Breakdown</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Panel 1: By Content Type */}
          <div className="card">
            <h4 className="font-medium mb-3 text-sm text-gray-600">By Content Type</h4>
            {sortedContentType.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sortedContentType.map((t) => ({
                  ...t,
                  name: (t.content_type || '').replace(/_/g, ' '),
                }))} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={100} />
                  <Tooltip />
                  <Bar dataKey="avg_engagement" fill="#D4A853" name="Avg Engagement" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-400 text-sm text-center py-8">No data yet.</p>
            )}
          </div>

          {/* Panel 2: By Format */}
          <div className="card">
            <h4 className="font-medium mb-3 text-sm text-gray-600">By Format</h4>
            {sortedFormat.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sortedFormat.map((f) => ({
                  ...f,
                  name: (f.format || '').replace(/_/g, ' '),
                }))} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={80} />
                  <Tooltip />
                  <Bar dataKey="avg_reach" fill="#2D4A3E" name="Avg Reach" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-400 text-sm text-center py-8">No data yet.</p>
            )}
          </div>

          {/* Panel 3: By Posting Time */}
          <div className="card">
            <h4 className="font-medium mb-3 text-sm text-gray-600">By Posting Time</h4>
            {timeData && timeData.length > 0 ? (
              <div className="grid grid-cols-2 gap-3 h-full items-center">
                <div className={`rounded-lg border-2 p-4 text-center ${
                  morningWins ? 'border-green-400 bg-green-50' : 'border-gray-200'
                }`}>
                  <div className="text-xs text-gray-500 mb-1">Morning</div>
                  <div className="text-xl font-bold font-heading">
                    {morningEng.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-500">avg engagement</div>
                  <div className="text-sm font-medium mt-2">
                    {(morning.avg_reach || 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500">avg reach</div>
                </div>
                <div className={`rounded-lg border-2 p-4 text-center ${
                  !morningWins ? 'border-green-400 bg-green-50' : 'border-gray-200'
                }`}>
                  <div className="text-xs text-gray-500 mb-1">Noon</div>
                  <div className="text-xl font-bold font-heading">
                    {noonEng.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-500">avg engagement</div>
                  <div className="text-sm font-medium mt-2">
                    {(noon.avg_reach || 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500">avg reach</div>
                </div>
              </div>
            ) : (
              <p className="text-gray-400 text-sm text-center py-8">No data yet.</p>
            )}
          </div>
        </div>
      </div>

      {/* Section 3: Competitor Activity */}
      <div>
        <h3 className="font-semibold text-lg mb-4">Competitor Activity</h3>
        {competitors && competitors.length > 0 ? (
          <div className="space-y-3">
            {competitors.map((comp) => (
              <CompetitorCard key={comp.handle} competitor={comp} />
            ))}
          </div>
        ) : (
          <div className="card text-center text-gray-400 py-8">
            <Users size={36} className="mx-auto mb-2 opacity-30" />
            <p>No competitor activity data yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function CompetitorCard({ competitor }) {
  const [expanded, setExpanded] = useState(false);
  const { handle, posts_per_week, dominant_format, format_distribution, recent_posts } = competitor;

  const formatDistData = format_distribution
    ? Object.entries(format_distribution).map(([key, value]) => ({
        name: key,
        count: value,
      }))
    : [];

  const total = formatDistData.reduce((sum, d) => sum + d.count, 0) || 1;

  return (
    <div className="card">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-4">
          <span className="font-medium text-brand-green">@{handle}</span>
          <span className="text-sm text-gray-500">
            {posts_per_week != null ? `${posts_per_week.toFixed(1)} posts/wk` : '--'}
          </span>
          {dominant_format && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
              {dominant_format}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && (
        <div className="mt-4 pt-4 border-t space-y-4">
          {/* Format Distribution */}
          {formatDistData.length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-gray-500 mb-2">Format Distribution</h5>
              <div className="flex rounded-full overflow-hidden h-5">
                {formatDistData.map((d) => (
                  <div
                    key={d.name}
                    style={{
                      width: `${(d.count / total) * 100}%`,
                      backgroundColor: FORMAT_COLORS[d.name] || '#9CA3AF',
                    }}
                    className="flex items-center justify-center text-white text-[10px] font-medium"
                    title={`${d.name}: ${d.count}`}
                  >
                    {(d.count / total) * 100 > 15 ? d.name.replace('_', ' ') : ''}
                  </div>
                ))}
              </div>
              <div className="flex gap-4 mt-1">
                {formatDistData.map((d) => (
                  <span key={d.name} className="text-[10px] text-gray-400 flex items-center gap-1">
                    <span
                      className="inline-block w-2 h-2 rounded-full"
                      style={{ backgroundColor: FORMAT_COLORS[d.name] || '#9CA3AF' }}
                    />
                    {d.name.replace('_', ' ')}: {d.count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Recent Posts Table */}
          {recent_posts && recent_posts.length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-gray-500 mb-2">Recent Posts</h5>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="pb-2 font-medium text-xs">Posted</th>
                      <th className="pb-2 font-medium text-xs">Type</th>
                      <th className="pb-2 font-medium text-xs">Caption Preview</th>
                      <th className="pb-2 font-medium text-xs text-right">Hashtags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent_posts.map((post, i) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-2 text-xs text-gray-500 whitespace-nowrap">
                          {post.posted_at
                            ? format(new Date(post.posted_at), 'MMM d')
                            : '--'}
                        </td>
                        <td className="py-2">
                          <span className="text-xs px-1.5 py-0.5 rounded font-medium"
                            style={{
                              backgroundColor: FORMAT_COLORS[post.media_type] ? `${FORMAT_COLORS[post.media_type]}20` : '#f3f4f6',
                              color: FORMAT_COLORS[post.media_type] || '#6b7280',
                            }}
                          >
                            {(post.media_type || '').replace('_', ' ')}
                          </span>
                        </td>
                        <td className="py-2 text-xs text-gray-600 max-w-[200px] truncate">
                          {post.caption_preview || '--'}
                        </td>
                        <td className="py-2 text-xs text-gray-400 text-right">
                          {post.hashtag_count ?? '--'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
