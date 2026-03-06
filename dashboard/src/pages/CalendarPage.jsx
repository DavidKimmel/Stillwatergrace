import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchWeeklyCalendar, postNow, rescheduleContent } from '../lib/api';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { format, addDays, subDays, startOfWeek } from 'date-fns';

const TYPE_COLORS = {
  marriage_monday: 'bg-pink-100 text-pink-700 border-pink-200',
  parenting_wednesday: 'bg-purple-100 text-purple-700 border-purple-200',
  faith_friday: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  daily_verse: 'bg-amber-100 text-amber-700 border-amber-200',
  encouragement: 'bg-green-100 text-green-700 border-green-200',
  prayer_prompt: 'bg-blue-100 text-blue-700 border-blue-200',
  gratitude: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  fill_in_blank: 'bg-orange-100 text-orange-700 border-orange-200',
  this_or_that: 'bg-teal-100 text-teal-700 border-teal-200',
  carousel: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  reel: 'bg-rose-100 text-rose-700 border-rose-200',
  conviction_quote: 'bg-gray-100 text-gray-700 border-gray-200',
};

const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  posted: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-700',
};

export default function CalendarPage() {
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(() => {
    const now = new Date();
    return startOfWeek(now, { weekStartsOn: 1 });
  });
  const [selectedItem, setSelectedItem] = useState(null);

  const startStr = format(weekStart, 'yyyy-MM-dd');

  const { data, isLoading } = useQuery({
    queryKey: ['calendar', startStr],
    queryFn: () => fetchWeeklyCalendar(startStr),
  });

  const postNowMut = useMutation({
    mutationFn: (id) => postNow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      setSelectedItem(null);
    },
  });

  const prevWeek = () => setWeekStart((d) => subDays(d, 7));
  const nextWeek = () => setWeekStart((d) => addDays(d, 7));

  const items = data?.items || [];

  const days = [];
  for (let i = 0; i < 7; i++) {
    const day = addDays(weekStart, i);
    const dateStr = format(day, 'yyyy-MM-dd');
    const dayItems = items.filter((item) => item.scheduled_at?.startsWith(dateStr));
    days.push({ date: day, items: dayItems });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-heading font-bold">Content Calendar</h2>
        <div className="flex items-center gap-3">
          <button onClick={prevWeek} className="p-2 hover:bg-gray-100 rounded-lg">
            <ChevronLeft size={18} />
          </button>
          <span className="text-sm font-medium min-w-[200px] text-center">
            {format(weekStart, 'MMM d')} — {format(addDays(weekStart, 6), 'MMM d, yyyy')}
          </span>
          <button onClick={nextWeek} className="p-2 hover:bg-gray-100 rounded-lg">
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-7 gap-2">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="card h-48 animate-pulse bg-gray-100" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-2">
          {days.map(({ date, items: dayItems }) => (
            <DayColumn
              key={date.toISOString()}
              date={date}
              items={dayItems}
              onSelectItem={setSelectedItem}
            />
          ))}
        </div>
      )}

      {/* Content Mix Meter */}
      <div className="card mt-6">
        <h3 className="font-semibold text-sm mb-3">Content Mix This Week</h3>
        <ContentMixMeter items={items} />
      </div>

      {/* Content Preview Modal */}
      {selectedItem && (
        <ContentPreviewModal
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onPostNow={(id) => postNowMut.mutate(id)}
          isPosting={postNowMut.isPending}
          queryClient={queryClient}
        />
      )}
    </div>
  );
}

function DayColumn({ date, items, onSelectItem }) {
  const isToday = format(date, 'yyyy-MM-dd') === format(new Date(), 'yyyy-MM-dd');

  return (
    <div className={`card p-3 min-h-[200px] ${isToday ? 'ring-2 ring-brand-gold' : ''}`}>
      <div className="text-center mb-3">
        <div className="text-xs text-gray-400 uppercase">{format(date, 'EEE')}</div>
        <div className={`text-lg font-bold ${isToday ? 'text-brand-gold' : 'text-brand-green'}`}>
          {format(date, 'd')}
        </div>
      </div>

      <div className="space-y-2">
        {items.length === 0 ? (
          <p className="text-xs text-gray-300 text-center">No content</p>
        ) : (
          items.map((item, i) => {
            const colorClass = TYPE_COLORS[item.content_type] || 'bg-gray-100 text-gray-700';
            const platforms = item.posting_status || {};
            const hasPosted = Object.values(platforms).some((p) => p.status === 'success');
            return (
              <div
                key={i}
                className={`p-2 rounded-lg border text-xs ${colorClass} cursor-pointer hover:ring-2 hover:ring-brand-gold/50 transition-all`}
                onClick={() => onSelectItem(item)}
              >
                <div className="font-medium truncate">
                  {item.content_type?.replace(/_/g, ' ')}
                </div>
                {item.scheduled_at && (
                  <div className="text-[10px] opacity-70 mt-0.5">
                    {format(new Date(item.scheduled_at), 'h:mm a')}
                  </div>
                )}
                {hasPosted && (
                  <div className="flex gap-1 mt-1">
                    {['instagram', 'facebook', 'tiktok'].map((p) => {
                      const ps = platforms[p];
                      if (!ps) return null;
                      const color = ps.status === 'success' ? 'text-green-600' : ps.status === 'failed' ? 'text-red-500' : 'text-gray-400';
                      return (
                        <span key={p} className={`text-[9px] font-bold ${color}`}>
                          {p.charAt(0).toUpperCase()}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function ContentPreviewModal({ item, onClose, onPostNow, isPosting, queryClient }) {
  const [newTime, setNewTime] = useState('');

  const rescheduleMut = useMutation({
    mutationFn: ({ id, time }) => rescheduleContent(id, time),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      onClose();
    },
  });

  const image = item.images?.find((img) => img.format === 'feed_4x5');
  const reel = item.images?.find((img) => img.format === 'reel_9x16');
  const platforms = item.posting_status || {};

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex justify-end" onClick={onClose}>
      <div
        className="bg-white w-full max-w-md h-full overflow-y-auto shadow-xl animate-slide-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[item.content_type]?.split(' ').slice(0, 2).join(' ') || 'bg-gray-100 text-gray-700'}`}>
                {item.content_type?.replace(/_/g, ' ')}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[item.status] || ''}`}>
                {item.status}
              </span>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X size={20} />
            </button>
          </div>

          {/* Image */}
          {image?.final_url && (
            <img src={image.final_url} alt="" className="w-full rounded-lg mb-4" />
          )}
          {reel?.final_url && (
            <video src={reel.final_url} controls className="w-full rounded-lg mb-4" />
          )}

          {/* Hook */}
          {item.hook && (
            <p className="font-heading font-bold text-lg mb-2 text-brand-green">{item.hook}</p>
          )}

          {/* Caption */}
          <p className="text-sm text-gray-600 mb-4 whitespace-pre-line">
            {item.caption_medium || item.caption_short || ''}
          </p>

          {/* Schedule */}
          <div className="text-xs text-gray-400 mb-2">
            Scheduled: {item.scheduled_at
              ? format(new Date(item.scheduled_at), 'EEE MMM d, h:mm a')
              : 'Not scheduled'}
          </div>

          {/* Reschedule */}
          {item.status !== 'posted' && (
            <div className="flex gap-2 mb-4">
              <input
                type="datetime-local"
                value={newTime}
                onChange={(e) => setNewTime(e.target.value)}
                className="border rounded-lg px-2 py-1 text-sm flex-1"
              />
              <button
                onClick={() => rescheduleMut.mutate({ id: item.id, time: newTime })}
                disabled={!newTime || rescheduleMut.isPending}
                className="px-3 py-1 text-sm border border-brand-green text-brand-green rounded-lg hover:bg-brand-green hover:text-white transition-colors disabled:opacity-50"
              >
                {rescheduleMut.isPending ? 'Saving...' : 'Reschedule'}
              </button>
            </div>
          )}

          {/* Platform Status */}
          <div className="border-t pt-4">
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
              Platform Status
            </h4>
            <div className="space-y-2">
              {['instagram', 'facebook', 'tiktok'].map((platform) => {
                const ps = platforms[platform];
                return (
                  <div key={platform} className="flex items-center justify-between text-sm">
                    <span className="capitalize">{platform}</span>
                    <PlatformBadge status={ps?.status} />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Post Now button */}
          {(item.status === 'pending' || item.status === 'approved') && (
            <button
              onClick={() => onPostNow(item.id)}
              disabled={isPosting}
              className="w-full mt-4 px-4 py-2 bg-brand-gold text-white rounded-lg font-medium hover:bg-brand-gold/90 disabled:opacity-50 transition-colors"
            >
              {isPosting ? 'Posting to all platforms...' : 'Post Now'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function PlatformBadge({ status }) {
  if (!status) return <span className="text-xs text-gray-300">--</span>;
  const styles = {
    success: 'text-green-600 bg-green-50',
    failed: 'text-red-600 bg-red-50',
    skipped: 'text-gray-400 bg-gray-50',
  };
  const cls = styles[status] || 'text-gray-400 bg-gray-50';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {status}
    </span>
  );
}

function ContentMixMeter({ items }) {
  const typeCounts = {};
  items.forEach((item) => {
    const type = item.content_type || 'unknown';
    typeCounts[type] = (typeCounts[type] || 0) + 1;
  });

  const total = items.length || 1;

  return (
    <div className="flex gap-1 h-4 rounded-full overflow-hidden bg-gray-100">
      {Object.entries(typeCounts).map(([type, count]) => {
        const colorClass = TYPE_COLORS[type]?.split(' ')[0] || 'bg-gray-200';
        const pct = (count / total) * 100;
        return (
          <div
            key={type}
            className={`${colorClass} transition-all`}
            style={{ width: `${pct}%` }}
            title={`${type.replace(/_/g, ' ')}: ${count}`}
          />
        );
      })}
    </div>
  );
}
