import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { addDays, differenceInCalendarDays, format, isToday, parseISO } from 'date-fns';
import { ChevronLeft, ChevronRight, Play, Clock } from 'lucide-react';
import {
  fetchWeeklyCalendar,
  selectPost,
  deletePost,
  approveContent,
  rejectContent,
  postNow,
  generateAiImage,
  swapReelImage,
  regenerateContent,
} from '../lib/api';
// PostDetailPanel removed — caption shown inline below thumbnail

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const TYPE_COLORS = {
  daily_verse: 'bg-blue-100 text-blue-700',
  marriage_monday: 'bg-pink-100 text-pink-700',
  faith_friday: 'bg-emerald-100 text-emerald-700',
  encouragement: 'bg-amber-100 text-amber-700',
  carousel: 'bg-cyan-100 text-cyan-700',
  christian_quote: 'bg-orange-100 text-orange-700',
};

const TYPE_LABELS = {
  daily_verse: 'Scripture',
  marriage_monday: 'Marriage',
  faith_friday: 'Faith',
  encouragement: 'Encouragement',
  carousel: 'Carousel',
  christian_quote: 'Quote',
};

const STATUS_STYLES = {
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-emerald-100 text-emerald-700',
  posted: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-700',
};

const STATUS_DOTS = {
  pending: 'bg-amber-500',
  approved: 'bg-emerald-500',
  posted: 'bg-blue-500',
  rejected: 'bg-red-500',
};

function groupPostsByDay(items, weekStart) {
  const grid = {};
  for (let d = 0; d < 7; d++) {
    grid[d] = [];
  }
  if (!items) return grid;

  items.forEach((item) => {
    if (!item.scheduled_at) return;
    const date = parseISO(item.scheduled_at);
    const dayOffset = differenceInCalendarDays(date, weekStart);
    if (dayOffset < 0 || dayOffset > 6) return;
    grid[dayOffset].push(item);
  });

  for (let d = 0; d < 7; d++) {
    grid[d].sort((a, b) => {
      const da = a.scheduled_at ? parseISO(a.scheduled_at) : new Date(0);
      const db = b.scheduled_at ? parseISO(b.scheduled_at) : new Date(0);
      return da - db;
    });
  }
  return grid;
}

function formatDateStr(date) {
  return format(date, 'yyyy-MM-dd');
}

function getPreviewImage(post) {
  if (!post?.images?.length) return null;
  const reel = post.images.find((img) => img.format === 'reel_9x16' && img.final_url);
  if (reel) return { url: reel.final_url, isReel: true };
  const feed = post.images.find((img) => img.final_url);
  if (feed) return { url: feed.final_url, isReel: false };
  return null;
}

function formatScheduledTime(scheduledAt) {
  if (!scheduledAt) return '';
  const d = parseISO(scheduledAt);
  const h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, '0');
  const period = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${m} ${period}`;
}

/* ── Week Strip Thumbnail ── */
function WeekStripDay({ dayIndex, dayDate, posts, isSelected, onSelect }) {
  const today = isToday(dayDate);
  const hasContent = posts.length > 0;
  const preview = hasContent ? getPreviewImage(posts[0]) : null;
  const statusDot = hasContent ? STATUS_DOTS[posts[0].status] || 'bg-gray-400' : null;

  return (
    <button
      onClick={() => onSelect(dayIndex)}
      className={`
        flex flex-col items-center gap-1 p-1.5 rounded-xl transition-all flex-1 min-w-0
        ${isSelected
          ? 'ring-2 ring-[#D4A853] bg-[#FFF8F0]'
          : today
            ? 'bg-[#D4A853]/5 hover:bg-[#D4A853]/10'
            : 'hover:bg-gray-100'
        }
      `}
    >
      <span className={`text-[10px] font-semibold uppercase tracking-wide ${
        isSelected ? 'text-[#D4A853]' : today ? 'text-[#D4A853]' : 'text-gray-500'
      }`}>
        {DAY_NAMES[dayIndex]}
      </span>

      {/* Mini thumbnail */}
      <div className={`w-12 h-12 rounded-lg overflow-hidden flex-shrink-0 ${
        isSelected ? 'ring-2 ring-[#D4A853]' : 'ring-1 ring-gray-200'
      }`}>
        {preview ? (
          <img src={preview.url} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-gray-100 flex items-center justify-center">
            <span className="text-[9px] text-gray-300">--</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        <span className={`text-[10px] ${
          isSelected ? 'text-[#D4A853] font-bold' : today ? 'text-[#D4A853] font-semibold' : 'text-gray-400'
        }`}>
          {format(dayDate, 'M/d')}
        </span>
        {statusDot && <span className={`w-1.5 h-1.5 rounded-full ${statusDot}`} />}
      </div>
    </button>
  );
}

export default function CalendarPage({ weekStart }) {
  const queryClient = useQueryClient();
  const [selectedDay, setSelectedDay] = useState(() => {
    // Default to today if it falls within this week, otherwise Monday
    const today = new Date();
    const offset = differenceInCalendarDays(today, weekStart);
    return (offset >= 0 && offset <= 6) ? offset : 0;
  });
  // detailContent state removed — no sidebar panel
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [toast, setToast] = useState(null);

  // Reset selected day when week changes
  useEffect(() => {
    const today = new Date();
    const offset = differenceInCalendarDays(today, weekStart);
    setSelectedDay((offset >= 0 && offset <= 6) ? offset : 0);
  }, [weekStart]);

  // Auto-dismiss toasts
  useEffect(() => {
    if (toast && toast.type !== 'loading') {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const startDateStr = formatDateStr(weekStart);

  const { data, isLoading, error } = useQuery({
    queryKey: ['calendar', startDateStr],
    queryFn: () => fetchWeeklyCalendar(startDateStr),
  });

  const items = data?.items || [];
  const grid = groupPostsByDay(items, weekStart);

  // (detail panel removed — caption inline)

  // Current day data
  const selectedDate = addDays(weekStart, selectedDay);
  const dayPosts = grid[selectedDay] || [];
  const primaryPost = dayPosts[0] || null;
  const preview = primaryPost ? getPreviewImage(primaryPost) : null;

  // Mutations
  const invalidateCalendar = () => queryClient.invalidateQueries({ queryKey: ['calendar'] });

  const selectMutation = useMutation({
    mutationFn: (id) => selectPost(id),
    onSuccess: invalidateCalendar,
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deletePost(id),
    onSuccess: () => {
      invalidateCalendar();
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id) => approveContent(id),
    onSuccess: invalidateCalendar,
  });

  const rejectMutation = useMutation({
    mutationFn: (id) => rejectContent(id),
    onSuccess: invalidateCalendar,
  });

  const postNowMutation = useMutation({
    mutationFn: (id) => {
      setToast({ message: 'Posting now...', type: 'loading' });
      return postNow(id);
    },
    onSuccess: () => {
      setToast({ message: 'Posted successfully', type: 'success' });
      invalidateCalendar();
    },
    onError: (err) => {
      setToast({ message: err.message || 'Post failed', type: 'error' });
    },
  });

  const aiImageMutation = useMutation({
    mutationFn: (id) => {
      setToast({ message: 'Generating AI image...', type: 'loading' });
      return generateAiImage(id);
    },
    onSuccess: () => {
      setToast({ message: 'AI image generated', type: 'success' });
      invalidateCalendar();
    },
    onError: (err) => {
      setToast({ message: err.message || 'AI image failed', type: 'error' });
    },
  });

  const swapReelMutation = useMutation({
    mutationFn: (id) => {
      setToast({ message: 'Swapping reel background...', type: 'loading' });
      return swapReelImage(id);
    },
    onSuccess: () => {
      setToast({ message: 'Reel swapped', type: 'success' });
      invalidateCalendar();
    },
    onError: (err) => {
      setToast({ message: err.message || 'Swap reel failed', type: 'error' });
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: (id) => {
      setToast({ message: 'Regenerating content...', type: 'loading' });
      return regenerateContent(id);
    },
    onSuccess: () => {
      setToast({ message: 'Content regenerated', type: 'success' });
      invalidateCalendar();
    },
    onError: (err) => {
      setToast({ message: err.message || 'Regenerate failed', type: 'error' });
    },
  });

  // Handlers
  const handleAction = (action, id) => {
    switch (action) {
      case 'approve':
        approveMutation.mutate(id);
        break;
      case 'reject':
        setConfirmDialog({
          action: 'reject',
          id,
          message: 'Are you sure you want to reject this post?',
        });
        break;
      case 'post-now':
        setConfirmDialog({
          action: 'post-now',
          id,
          message: 'Post this content now to Instagram and Facebook?',
        });
        break;
      case 'delete':
        setConfirmDialog({
          action: 'delete',
          id,
          message: 'Are you sure you want to delete this post? This cannot be undone.',
        });
        break;
      case 'ai-image':
        aiImageMutation.mutate(id);
        break;
      case 'swap-reel':
        swapReelMutation.mutate(id);
        break;
      case 'regenerate':
        regenerateMutation.mutate(id);
        break;
      case 'view-details':
        // no-op — detail shown inline now
        break;
      default:
        break;
    }
  };

  const handleConfirmAction = () => {
    if (!confirmDialog) return;
    if (confirmDialog.action === 'reject') {
      rejectMutation.mutate(confirmDialog.id);
    } else if (confirmDialog.action === 'delete') {
      deleteMutation.mutate(confirmDialog.id);
    } else if (confirmDialog.action === 'post-now') {
      postNowMutation.mutate(confirmDialog.id);
    }
    setConfirmDialog(null);
  };

  const navigateDay = (delta) => {
    setSelectedDay((prev) => {
      const next = prev + delta;
      if (next < 0 || next > 6) return prev;
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-[#D4A853] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-sm text-gray-500">Loading calendar...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-sm text-red-500">Failed to load calendar</p>
          <p className="text-xs text-gray-400 mt-1">{error.message}</p>
        </div>
      </div>
    );
  }

  const typeColor = primaryPost
    ? (TYPE_COLORS[primaryPost.content_type] || 'bg-gray-100 text-gray-700')
    : '';
  const typeLabel = primaryPost
    ? (TYPE_LABELS[primaryPost.content_type] || primaryPost.content_type)
    : '';
  const statusStyle = primaryPost
    ? (STATUS_STYLES[primaryPost.status] || 'bg-gray-100 text-gray-600')
    : '';

  return (
    <div className="h-full flex flex-col">
      {/* ── Week Strip ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-2 mb-4">
        <div className="flex gap-1">
          {Array.from({ length: 7 }, (_, i) => (
            <WeekStripDay
              key={i}
              dayIndex={i}
              dayDate={addDays(weekStart, i)}
              posts={grid[i] || []}
              isSelected={selectedDay === i}
              onSelect={setSelectedDay}
            />
          ))}
        </div>
      </div>

      {/* ── Main Content Area ── */}
      <div className="flex-1 flex flex-col items-center">
        {/* Day Navigation Header */}
        <div className="flex items-center gap-4 mb-5">
          <button
            onClick={() => navigateDay(-1)}
            disabled={selectedDay === 0}
            className="p-2 rounded-lg hover:bg-gray-100 text-[#2D4A3E] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={22} />
          </button>

          <div className="text-center min-w-[220px]">
            <h2 className="text-lg font-heading font-semibold text-[#2D4A3E]">
              {format(selectedDate, 'EEEE, MMMM d')}
            </h2>
            {isToday(selectedDate) && (
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[#D4A853]">Today</span>
            )}
          </div>

          <button
            onClick={() => navigateDay(1)}
            disabled={selectedDay === 6}
            className="p-2 rounded-lg hover:bg-gray-100 text-[#2D4A3E] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight size={22} />
          </button>
        </div>

        {primaryPost ? (
          <div className="flex flex-col items-center w-full max-w-lg">
            {/* Badges row */}
            <div className="flex items-center gap-2 mb-3">
              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${typeColor}`}>
                {typeLabel}
              </span>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full capitalize ${statusStyle}`}>
                {primaryPost.status}
              </span>
              {primaryPost.scheduled_at && (
                <span className="flex items-center gap-1 text-xs text-gray-500">
                  <Clock size={12} />
                  {formatScheduledTime(primaryPost.scheduled_at)}
                </span>
              )}
            </div>

            {/* Large Thumbnail */}
            <div
              className="relative w-full max-w-[420px] aspect-square rounded-2xl overflow-hidden bg-gray-100 shadow-lg"
            >
              {preview ? (
                <>
                  <img
                    src={preview.url}
                    alt=""
                    className="w-full h-full object-contain"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                  {preview.isReel && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/10 group-hover:bg-black/20 transition-colors">
                      <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                        <Play size={24} className="text-[#2D4A3E] fill-[#2D4A3E] ml-1" />
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-300">
                  <span className="text-sm">No image</span>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
              {primaryPost.status === 'pending' && (
                <>
                  <button
                    onClick={() => handleAction('approve', primaryPost.id)}
                    className="px-5 py-2.5 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleAction('reject', primaryPost.id)}
                    className="px-5 py-2.5 text-sm font-medium bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                  >
                    Reject
                  </button>
                </>
              )}
              {primaryPost.status === 'approved' && (
                <button
                  onClick={() => handleAction('post-now', primaryPost.id)}
                  className="px-5 py-2.5 text-sm font-medium bg-[#D4A853] text-white rounded-lg hover:bg-[#b8903a] transition-colors"
                >
                  Post Now
                </button>
              )}
              <button
                onClick={() => handleAction('regenerate', primaryPost.id)}
                className="px-5 py-2.5 text-sm font-medium border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Regenerate
              </button>
            </div>

            {/* Caption */}
            {(primaryPost.caption_short || primaryPost.caption_medium || primaryPost.caption_long) && (
              <div className="mt-4 w-full max-w-md">
                <p className="text-sm text-[#2D4A3E] leading-relaxed whitespace-pre-line">
                  {(primaryPost.caption_short || primaryPost.caption_medium || primaryPost.caption_long || '')
                    .split('\n')
                    .filter(line => !line.trim().startsWith('#') || line.trim().split(/\s+/).filter(w => w.startsWith('#')).length <= 5)
                    .map((line, i) => {
                      // If line is all hashtags, limit to 5
                      const words = line.trim().split(/\s+/);
                      if (words.length > 0 && words.every(w => w.startsWith('#'))) {
                        return words.slice(0, 5).join(' ');
                      }
                      return line;
                    })
                    .join('\n')
                  }
                </p>
              </div>
            )}

            {/* Additional posts for this day (if more than 1) */}
            {dayPosts.length > 1 && (
              <div className="mt-6 w-full border-t pt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 text-center">
                  {dayPosts.length} posts this day
                </p>
                <div className="flex gap-3 justify-center">
                  {dayPosts.map((post, i) => {
                    const img = getPreviewImage(post);
                    const isActive = i === 0;
                    return (
                      <button
                        key={post.id}
                        onClick={() => {}}
                        className={`
                          w-16 h-20 rounded-lg overflow-hidden flex-shrink-0 transition-all
                          ${isActive
                            ? 'ring-2 ring-[#D4A853] shadow-md'
                            : 'ring-1 ring-gray-200 hover:ring-[#D4A853]/50'
                          }
                        `}
                      >
                        {img ? (
                          <img src={img.url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full bg-gray-100 flex items-center justify-center text-[9px] text-gray-300">
                            --
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Empty day state */
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-24 h-24 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
              <span className="text-3xl text-gray-300">--</span>
            </div>
            <p className="text-sm text-gray-500 mb-1">No content scheduled</p>
            <p className="text-xs text-gray-400 mb-4">
              {format(selectedDate, 'EEEE, MMMM d')}
            </p>
          </div>
        )}
      </div>

      {/* Confirm dialog */}
      {confirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-[340px]">
            <h3 className="text-sm font-semibold text-[#2D4A3E] mb-2">
              {confirmDialog.action === 'delete' ? 'Delete Post' : confirmDialog.action === 'post-now' ? 'Post Now' : 'Reject Post'}
            </h3>
            <p className="text-sm text-gray-600 mb-5">{confirmDialog.message}</p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDialog(null)}
                className="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                className={`flex-1 px-4 py-2 text-sm text-white rounded-lg transition-colors ${
                  confirmDialog.action === 'delete'
                    ? 'bg-red-600 hover:bg-red-700'
                    : confirmDialog.action === 'post-now'
                      ? 'bg-[#D4A853] hover:bg-[#b8903a]'
                      : 'bg-amber-500 hover:bg-amber-600'
                }`}
              >
                {confirmDialog.action === 'delete' ? 'Delete' : confirmDialog.action === 'post-now' ? 'Post Now' : 'Reject'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-sm ${
          toast.type === 'loading'
            ? 'bg-[#2D4A3E] text-white'
            : toast.type === 'success'
              ? 'bg-emerald-600 text-white'
              : 'bg-red-600 text-white'
        }`}>
          {toast.type === 'loading' && (
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          {toast.message}
          {toast.type !== 'loading' && (
            <button
              onClick={() => setToast(null)}
              className="ml-2 text-white/70 hover:text-white text-xs"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      {/* Detail panel removed — caption shown inline */}
    </div>
  );
}
