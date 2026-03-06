import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchContentQueue, approveContent, rejectContent, bulkApprove, postNow } from '../lib/api';
import ContentCard from '../components/ContentCard';
import { Check, X, Filter } from 'lucide-react';

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

const TYPE_OPTIONS = [
  { value: '', label: 'All Types' },
  { value: 'daily_verse', label: 'Daily Verse' },
  { value: 'marriage_monday', label: 'Marriage Monday' },
  { value: 'parenting_wednesday', label: 'Parenting Wednesday' },
  { value: 'faith_friday', label: 'Faith Friday' },
  { value: 'encouragement', label: 'Encouragement' },
  { value: 'fill_in_blank', label: 'Fill in Blank' },
  { value: 'this_or_that', label: 'This or That' },
  { value: 'reel', label: 'Reel' },
  { value: 'carousel', label: 'Carousel' },
];

export default function QueuePage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState(new Set());

  const params = {};
  if (statusFilter) params.status = statusFilter;
  if (typeFilter) params.content_type = typeFilter;

  const { data, isLoading } = useQuery({
    queryKey: ['content-queue', params],
    queryFn: () => fetchContentQueue(params),
  });

  const approveMut = useMutation({
    mutationFn: (id) => approveContent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['content-queue'] }),
  });

  const rejectMut = useMutation({
    mutationFn: (id) => rejectContent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['content-queue'] }),
  });

  const bulkApproveMut = useMutation({
    mutationFn: (ids) => bulkApprove(ids),
    onSuccess: () => {
      setSelectedIds(new Set());
      queryClient.invalidateQueries({ queryKey: ['content-queue'] });
    },
  });

  const postNowMut = useMutation({
    mutationFn: (id) => postNow(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['content-queue'] }),
  });

  const toggleSelect = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const items = data?.items || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-heading font-bold">Content Queue</h2>
        <span className="text-sm text-gray-500">{data?.total || 0} items</span>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6 flex-wrap items-center">
        <Filter size={16} className="text-gray-400" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm bg-white"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm bg-white"
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {selectedIds.size > 0 && (
          <button
            onClick={() => bulkApproveMut.mutate([...selectedIds])}
            className="btn-primary text-sm ml-auto"
            disabled={bulkApproveMut.isPending}
          >
            <Check size={14} className="inline mr-1" />
            Approve {selectedIds.size} Selected
          </button>
        )}
      </div>

      {/* Content Cards */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card h-48 animate-pulse bg-gray-100" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="card text-center text-gray-400 py-12">
          No content in queue. Run the generation pipeline to create content.
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <ContentCard
              key={item.id}
              content={item}
              selected={selectedIds.has(item.id)}
              onToggleSelect={() => toggleSelect(item.id)}
              onApprove={() => approveMut.mutate(item.id)}
              onReject={() => rejectMut.mutate(item.id)}
              onPostNow={() => postNowMut.mutate(item.id)}
              isApproving={approveMut.isPending}
              isRejecting={rejectMut.isPending}
              isPosting={postNowMut.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}
