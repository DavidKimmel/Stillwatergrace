import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { Sparkles, ArrowRight } from 'lucide-react';

import KpiRow from '../components/KpiRow.jsx';
import CompetitorCard from '../components/CompetitorCard.jsx';
import PerformanceChart from '../components/PerformanceChart.jsx';
import {
  fetchAnalyticsOverview,
  fetchTopPosts,
  fetchInsightsRecommendations,
  fetchInsightsCompetitors,
  fetchPostingHistory,
  getTopCompetitorPosts,
} from '../lib/api.js';

// ── Helpers ──

const PRIORITY_STYLES = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-emerald-100 text-emerald-700',
};

function priorityLabel(confidence) {
  const map = { high: 'HIGH', medium: 'MEDIUM', low: 'LOW' };
  return map[confidence] || 'INFO';
}

function formatContentType(type) {
  return (type || '')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// ── Section A: Competitor Intelligence ──

function CompetitorSection() {
  const [handleFilter, setHandleFilter] = useState('');
  const [mediaFilter, setMediaFilter] = useState('');
  const navigate = useNavigate();

  const { data: topPosts } = useQuery({
    queryKey: ['competitorTopPosts'],
    queryFn: () => getTopCompetitorPosts(),
  });

  const { data: competitors } = useQuery({
    queryKey: ['insightsCompetitors'],
    queryFn: () => fetchInsightsCompetitors(),
  });

  const posts = topPosts?.posts || [];
  const handles = useMemo(() => {
    const set = new Set(posts.map((p) => p.handle));
    return [...set].sort();
  }, [posts]);

  const mediaTypes = useMemo(() => {
    const set = new Set(posts.map((p) => p.media_type));
    return [...set].sort();
  }, [posts]);

  const filtered = useMemo(() => {
    let result = posts;
    if (handleFilter) {
      result = result.filter((p) => p.handle === handleFilter);
    }
    if (mediaFilter) {
      result = result.filter((p) => p.media_type === mediaFilter);
    }
    return result;
  }, [posts, handleFilter, mediaFilter]);

  const handleInspire = (post) => {
    navigate('/creator', { state: { inspireFrom: post } });
  };

  return (
    <section>
      <h2 className="font-heading text-xl text-brand-green mb-4">Top Competitor Posts</h2>

      {/* Filter row */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={handleFilter}
          onChange={(e) => setHandleFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-gold/40"
        >
          <option value="">All Competitors</option>
          {handles.map((h) => (
            <option key={h} value={h}>@{h}</option>
          ))}
        </select>

        <select
          value={mediaFilter}
          onChange={(e) => setMediaFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-gold/40"
        >
          <option value="">All Media Types</option>
          {mediaTypes.map((t) => (
            <option key={t} value={t}>{t === 'CAROUSEL_ALBUM' ? 'Carousel' : t.charAt(0) + t.slice(1).toLowerCase()}</option>
          ))}
        </select>
      </div>

      {/* Competitor summary from insights */}
      {competitors && competitors.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-3">
          {competitors.map((c) => (
            <div
              key={c.handle}
              className="bg-white rounded-xl px-4 py-3 shadow-sm border border-gray-100 text-sm"
            >
              <span className="font-medium text-brand-green">@{c.handle}</span>
              <span className="text-gray-500 ml-2">{c.posts_per_week}/wk</span>
              <span className="text-gray-400 ml-2">
                {Object.entries(c.format_distribution || {})
                  .map(([k, v]) => `${k === 'CAROUSEL_ALBUM' ? 'Carousel' : k.charAt(0) + k.slice(1).toLowerCase()} ${v}%`)
                  .join(' / ')}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Cards grid */}
      {filtered.length === 0 ? (
        <p className="text-sm text-gray-400">No competitor posts found.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((post, i) => (
            <CompetitorCard
              key={`${post.handle}-${i}`}
              post={post}
              handle={post.handle}
              onInspire={handleInspire}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// ── Section B: Performance ──

function PerformanceSection() {
  const navigate = useNavigate();

  const { data: overview } = useQuery({
    queryKey: ['analyticsOverview', 30],
    queryFn: () => fetchAnalyticsOverview(30),
  });

  const { data: bestPosts } = useQuery({
    queryKey: ['topPosts', 30],
    queryFn: () => fetchTopPosts(30, 'saves', 10),
  });

  const { data: postingHistory } = useQuery({
    queryKey: ['postingHistory', 30],
    queryFn: () => fetchPostingHistory(30),
  });

  // Transform overview into KpiRow data
  const kpiData = overview
    ? {
        reach: overview.total_reach,
        engagement_rate: overview.avg_engagement_rate,
        likes: overview.total_likes,
        saves: overview.total_saves,
        shares: overview.total_shares,
        deltas: overview.deltas || {},
      }
    : null;

  // Transform posting history into chart data
  const chartData = useMemo(() => {
    if (!postingHistory || !Array.isArray(postingHistory)) return [];
    return postingHistory.map((item) => ({
      date: item.date || item.scheduled_at?.slice(0, 10) || '',
      reach: item.reach || 0,
      engagement: item.engagement_rate ? Math.round(item.engagement_rate * 1000) : 0,
      likes: item.likes || 0,
      content_type: item.content_type,
    }));
  }, [postingHistory]);

  const handleRemix = (post) => {
    navigate('/creator', { state: { remixFrom: post } });
  };

  return (
    <section>
      <h2 className="font-heading text-xl text-brand-green mb-4">Performance</h2>

      {/* KPI row */}
      <KpiRow data={kpiData} />

      {/* Chart */}
      <div className="mt-6">
        <PerformanceChart data={chartData} />
      </div>

      {/* Best Performing Posts table */}
      {bestPosts && bestPosts.length > 0 && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h3 className="font-heading text-lg text-brand-green">Best Performing Posts</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 text-xs uppercase tracking-wider">
                  <th className="px-6 py-3">Hook</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Reach</th>
                  <th className="px-6 py-3">Engagement</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {bestPosts.map((post) => (
                  <tr key={post.content_id} className="hover:bg-brand-cream/30 transition-colors">
                    <td className="px-6 py-3 max-w-[240px] truncate text-gray-700">
                      {post.hook}
                    </td>
                    <td className="px-6 py-3 text-gray-500">
                      {formatContentType(post.content_type)}
                    </td>
                    <td className="px-6 py-3 text-gray-700">
                      {(post.reach || 0).toLocaleString()}
                    </td>
                    <td className="px-6 py-3 text-gray-700">
                      {((post.engagement_rate || 0) * 100).toFixed(1)}%
                    </td>
                    <td className="px-6 py-3 text-gray-400">
                      {post.scheduled_at
                        ? format(new Date(post.scheduled_at), 'MMM d')
                        : '--'}
                    </td>
                    <td className="px-6 py-3">
                      <button
                        onClick={() => handleRemix(post)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-brand-gold hover:text-brand-gold-dark transition-colors"
                      >
                        Remix <ArrowRight size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Section C: Recommendations ──

function RecommendationsSection() {
  const { data: recommendations } = useQuery({
    queryKey: ['insightsRecommendations', 30],
    queryFn: () => fetchInsightsRecommendations(30),
  });

  if (!recommendations || recommendations.length === 0) {
    return (
      <section>
        <h2 className="font-heading text-xl text-brand-green mb-4">AI Recommendations</h2>
        <p className="text-sm text-gray-400">No recommendations available yet.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={20} className="text-brand-gold" />
        <h2 className="font-heading text-xl text-brand-green">AI Recommendations</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {recommendations.map((rec, i) => {
          const priority = rec.confidence || 'medium';
          const badgeStyle = PRIORITY_STYLES[priority] || PRIORITY_STYLES.medium;

          return (
            <div
              key={i}
              className="bg-white rounded-xl p-5 shadow-sm border border-gray-100"
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <h4 className="font-medium text-brand-green text-sm">{rec.title}</h4>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${badgeStyle}`}>
                  {priorityLabel(priority)}
                </span>
              </div>
              <p className="text-sm text-gray-600 leading-relaxed">{rec.why}</p>
              {rec.source && (
                <span className="inline-block mt-2 text-xs text-gray-400 capitalize">
                  Source: {rec.source}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── Main Page ──

export default function InsightsPage() {
  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-heading text-2xl text-brand-green mb-1">Insights</h1>
        <p className="text-sm text-gray-500">
          Competitor intelligence, performance metrics, and AI-powered recommendations.
        </p>
      </div>

      <CompetitorSection />

      <hr className="border-gray-100" />

      <PerformanceSection />

      <hr className="border-gray-100" />

      <RecommendationsSection />
    </div>
  );
}
