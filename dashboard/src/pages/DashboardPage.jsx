import { useQuery } from '@tanstack/react-query';
import { fetchDashboardOverview } from '../lib/api';
import MetricCard from '../components/MetricCard';
import { ListChecks, Send, AlertCircle, DollarSign } from 'lucide-react';

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: fetchDashboardOverview,
  });

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  const q = data?.content_queue || {};
  const p = data?.posting_this_week || {};

  return (
    <div>
      <h2 className="text-2xl font-heading font-bold mb-6">Dashboard</h2>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          icon={ListChecks}
          label="Pending Review"
          value={q.pending || 0}
          color="yellow"
        />
        <MetricCard
          icon={Send}
          label="Scheduled Today"
          value={q.scheduled_today || 0}
          color="blue"
        />
        <MetricCard
          icon={AlertCircle}
          label="Posted This Week"
          value={p.successful || 0}
          sublabel={p.failed ? `${p.failed} failed` : undefined}
          color="green"
        />
        <MetricCard
          icon={DollarSign}
          label="Revenue This Month"
          value={`$${data?.revenue_this_month || 0}`}
          color="gold"
        />
      </div>

      {/* Platform Breakdown */}
      <div className="card mb-6">
        <h3 className="font-semibold text-lg mb-4">This Week by Platform</h3>
        <div className="grid grid-cols-3 gap-4">
          {['instagram', 'facebook', 'tiktok'].map((p) => {
            const stats = (data?.posting_by_platform || {})[p] || { successful: 0, failed: 0 };
            return (
              <div key={p} className="text-center p-3 rounded-lg bg-gray-50">
                <div className="text-xs text-gray-500 uppercase mb-1">{p}</div>
                <div className="text-xl font-bold text-brand-green">{stats.successful}</div>
                {stats.failed > 0 && (
                  <div className="text-xs text-red-500 mt-1">{stats.failed} failed</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="font-semibold text-lg mb-4">Quick Actions</h3>
        <div className="flex gap-3 flex-wrap">
          <a href="/queue" className="btn-primary">Review Content Queue</a>
          <a href="/calendar" className="btn-outline">View Calendar</a>
          <a href="/analytics" className="btn-outline">Weekly Analytics</a>
        </div>
      </div>

      {/* Status Indicators */}
      <div className="mt-6 card">
        <h3 className="font-semibold text-lg mb-4">System Status</h3>
        <div className="space-y-2 text-sm">
          <StatusRow label="Content Pipeline" status="active" />
          <StatusRow label="Image Generation" status="active" />
          <StatusRow label="Instagram API" status={q.scheduled_today > 0 ? 'active' : 'idle'} />
          <StatusRow label="Analytics Collection" status="active" />
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, status }) {
  const colors = {
    active: 'bg-green-400',
    idle: 'bg-gray-300',
    error: 'bg-red-400',
  };

  return (
    <div className="flex items-center gap-3">
      <span className={`w-2 h-2 rounded-full ${colors[status] || colors.idle}`} />
      <span className="text-gray-600">{label}</span>
      <span className="text-xs text-gray-400 ml-auto capitalize">{status}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div>
      <div className="h-8 w-40 bg-gray-200 rounded mb-6 animate-pulse" />
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card h-24 animate-pulse bg-gray-100" />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message }) {
  return (
    <div className="card border-red-200 bg-red-50 text-red-800">
      <p className="font-semibold">Failed to load dashboard</p>
      <p className="text-sm mt-1">{message}</p>
      <p className="text-xs mt-2 text-red-600">
        Make sure the API server is running (uvicorn api.main:app)
      </p>
    </div>
  );
}
