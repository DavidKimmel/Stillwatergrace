import { useQuery } from '@tanstack/react-query';
import {
  fetchRevenueSummary,
  fetchAffiliateLinks,
  fetchBrandDeals,
  fetchSubscriberStats,
} from '../lib/api';
import MetricCard from '../components/MetricCard';
import { DollarSign, Link2, Users, Briefcase } from 'lucide-react';

const STAGE_COLORS = {
  prospect: 'bg-gray-100 text-gray-600',
  contacted: 'bg-blue-100 text-blue-700',
  negotiating: 'bg-yellow-100 text-yellow-700',
  closed_won: 'bg-green-100 text-green-700',
  closed_lost: 'bg-red-100 text-red-600',
};

export default function MonetizationPage() {
  const { data: revenue } = useQuery({
    queryKey: ['revenue-summary'],
    queryFn: () => fetchRevenueSummary(6),
  });

  const { data: affiliates } = useQuery({
    queryKey: ['affiliates'],
    queryFn: fetchAffiliateLinks,
  });

  const { data: deals } = useQuery({
    queryKey: ['brand-deals'],
    queryFn: () => fetchBrandDeals(),
  });

  const { data: subscribers } = useQuery({
    queryKey: ['subscribers'],
    queryFn: fetchSubscriberStats,
  });

  const r = revenue || {};

  return (
    <div>
      <h2 className="text-2xl font-heading font-bold mb-6">Monetization</h2>

      {/* Revenue Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          icon={DollarSign}
          label="Total Revenue"
          value={`$${(r.total_revenue || 0).toFixed(2)}`}
          color="gold"
        />
        <MetricCard
          icon={Link2}
          label="Affiliate Links"
          value={(affiliates || []).length}
          color="blue"
        />
        <MetricCard
          icon={Briefcase}
          label="Brand Contacts"
          value={(deals || []).length}
          color="green"
        />
        <MetricCard
          icon={Users}
          label="Email Subscribers"
          value={subscribers?.total_active || 0}
          color="yellow"
        />
      </div>

      {/* Revenue by Source */}
      {r.by_source && r.by_source.length > 0 && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Revenue by Source</h3>
          <div className="space-y-3">
            {r.by_source.map((src) => (
              <div key={src.source} className="flex items-center justify-between">
                <div>
                  <span className="font-medium capitalize">{src.source}</span>
                  <span className="text-xs text-gray-400 ml-2">{src.transactions} transactions</span>
                </div>
                <span className="font-bold text-brand-gold">${src.total.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Affiliate Links */}
        <div className="card">
          <h3 className="font-semibold mb-4">Affiliate Links</h3>
          {(affiliates || []).length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-6">
              No affiliate links yet. Add links via the API.
            </p>
          ) : (
            <div className="space-y-3">
              {affiliates.map((link) => (
                <div key={link.id} className="flex items-center justify-between border-b border-gray-50 pb-2">
                  <div>
                    <p className="font-medium text-sm">{link.product_name}</p>
                    <p className="text-xs text-gray-400">{link.program} — {link.commission_rate}%</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{link.clicks} clicks</p>
                    <p className="text-xs text-green-600">{link.conversions} conversions</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Brand Pipeline */}
        <div className="card">
          <h3 className="font-semibold mb-4">Brand Pipeline</h3>
          {(deals || []).length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-6">
              No brand contacts yet. Seed prospects via <code>python manage.py seed</code>.
            </p>
          ) : (
            <div className="space-y-3">
              {deals.slice(0, 10).map((deal) => (
                <div key={deal.id} className="flex items-center justify-between border-b border-gray-50 pb-2">
                  <div>
                    <p className="font-medium text-sm">{deal.brand_name}</p>
                    <p className="text-xs text-gray-400">{deal.category}</p>
                  </div>
                  <span className={`badge text-xs ${STAGE_COLORS[deal.deal_stage] || ''}`}>
                    {(deal.deal_stage || '').replace(/_/g, ' ')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
