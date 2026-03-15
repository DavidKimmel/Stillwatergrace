import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DndContext, DragOverlay, useDroppable, pointerWithin } from '@dnd-kit/core';
import { addDays, differenceInCalendarDays, format, isToday, parseISO } from 'date-fns';
import {
  fetchWeeklyCalendar,
  selectPost,
  movePost,
  deletePost,
  approveContent,
  rejectContent,
  postNow,
  generateAiImage,
  swapReelImage,
} from '../lib/api';
import CalendarCard from '../components/CalendarCard';
import PostDetailPanel from '../components/PostDetailPanel';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function formatTime12h(hour, minute) {
  const period = hour >= 12 ? 'PM' : 'AM';
  const h = hour % 12 || 12;
  const m = String(minute).padStart(2, '0');
  return `${h}:${m} ${period}`;
}

function getTimeKey(scheduledAt) {
  if (!scheduledAt) return '06:30';
  const date = typeof scheduledAt === 'string' ? parseISO(scheduledAt) : scheduledAt;
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

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

  // Sort each day's posts by scheduled time
  for (let d = 0; d < 7; d++) {
    grid[d].sort((a, b) => {
      const da = a.scheduled_at ? parseISO(a.scheduled_at) : new Date(0);
      const db = b.scheduled_at ? parseISO(b.scheduled_at) : new Date(0);
      return da - db;
    });
  }

  return grid;
}

function formatDate(date) {
  return format(date, 'yyyy-MM-dd');
}

function DroppableDay({ id, children, isOver }) {
  const { setNodeRef, isOver: dndIsOver } = useDroppable({ id });
  const highlight = isOver || dndIsOver;
  return (
    <div
      ref={setNodeRef}
      className={`min-h-[300px] p-1.5 rounded-lg transition-colors flex-1 ${
        highlight ? 'bg-[#D4A853]/10 ring-2 ring-[#D4A853]/30' : ''
      }`}
    >
      {children}
    </div>
  );
}

/* ── Time Picker Modal ── */
function TimePickerModal({ dayDate, onConfirm, onCancel }) {
  const [hour, setHour] = useState('06');
  const [minute, setMinute] = useState('30');

  const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
  const minutes = ['00', '15', '30', '45'];

  const handleConfirm = () => {
    onConfirm(`${hour}:${minute}`);
  };

  const presets = [
    { label: '6:30 AM', h: '06', m: '30' },
    { label: '12:00 PM', h: '12', m: '00' },
    { label: '4:00 PM', h: '16', m: '00' },
    { label: '7:00 PM', h: '19', m: '00' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-[320px]">
        <h3 className="text-sm font-semibold text-[#2D4A3E] mb-1">
          Schedule Time
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          {format(dayDate, 'EEEE, MMM d')}
        </p>

        {/* Quick presets */}
        <div className="flex flex-wrap gap-2 mb-4">
          {presets.map((p) => (
            <button
              key={p.label}
              onClick={() => { setHour(p.h); setMinute(p.m); }}
              className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                hour === p.h && minute === p.m
                  ? 'bg-[#D4A853] text-white border-[#D4A853]'
                  : 'border-gray-300 text-gray-600 hover:border-[#D4A853] hover:text-[#D4A853]'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Custom time selectors */}
        <div className="flex items-center gap-2 mb-5">
          <select
            value={hour}
            onChange={(e) => setHour(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-[#2D4A3E] focus:outline-none focus:ring-2 focus:ring-[#D4A853]/40"
          >
            {hours.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
          <span className="text-lg font-bold text-gray-400">:</span>
          <select
            value={minute}
            onChange={(e) => setMinute(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-[#2D4A3E] focus:outline-none focus:ring-2 focus:ring-[#D4A853]/40"
          >
            {minutes.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <span className="text-xs text-gray-500 ml-1">
            ({formatTime12h(parseInt(hour, 10), parseInt(minute, 10))})
          </span>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="flex-1 px-4 py-2 text-sm bg-[#2D4A3E] text-white rounded-lg hover:bg-[#2D4A3E]/90 transition-colors"
          >
            Set Time
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CalendarPage({ weekStart }) {
  const queryClient = useQueryClient();
  const [selectedPostId, setSelectedPostId] = useState(null);
  const [detailContent, setDetailContent] = useState(null);
  const [activeDragId, setActiveDragId] = useState(null);
  const [timePicker, setTimePicker] = useState(null); // { postId, dayIndex }
  const [confirmDialog, setConfirmDialog] = useState(null); // { action, id, message }
  const [toast, setToast] = useState(null); // { message, type }

  // Auto-dismiss success/error toasts after 3s
  useEffect(() => {
    if (toast && toast.type !== 'loading') {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const startDateStr = formatDate(weekStart);

  const { data, isLoading, error } = useQuery({
    queryKey: ['calendar', startDateStr],
    queryFn: () => fetchWeeklyCalendar(startDateStr),
  });

  const items = data?.items || [];
  const grid = groupPostsByDay(items, weekStart);

  // Sync detail panel with latest data after mutations (AI Image, Swap Reel, etc.)
  useEffect(() => {
    if (!detailContent || !data?.items) return;
    const updated = data.items.find((item) => item.id === detailContent.id);
    if (updated) {
      setDetailContent(updated);
    }
  }, [data]);

  // Find the dragged item for the overlay
  const activeDragItem = activeDragId
    ? items.find((item) => item.id === activeDragId)
    : null;

  // Mutations
  const invalidateCalendar = () => queryClient.invalidateQueries({ queryKey: ['calendar'] });

  const selectMutation = useMutation({
    mutationFn: (id) => selectPost(id),
    onSuccess: invalidateCalendar,
  });

  const moveMutation = useMutation({
    mutationFn: ({ id, date, time }) => movePost(id, date, time),
    onSuccess: invalidateCalendar,
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deletePost(id),
    onSuccess: () => {
      if (detailContent?.id === deleteMutation.variables) {
        setDetailContent(null);
      }
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

  // Handlers
  const handleSelect = (id) => {
    setSelectedPostId((prev) => (prev === id ? null : id));
    selectMutation.mutate(id);
  };

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
      case 'view-details': {
        const post = items.find((item) => item.id === id);
        setDetailContent(post || null);
        break;
      }
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

  const handleDragStart = (event) => {
    setActiveDragId(event.active.id);
  };

  const handleDragEnd = (event) => {
    setActiveDragId(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    // over.id format: "day-{dayIndex}"
    const overId = String(over.id);
    if (!overId.startsWith('day-')) return;

    const dayIndex = parseInt(overId.split('-')[1], 10);
    if (isNaN(dayIndex) || dayIndex < 0 || dayIndex > 6) return;

    // Open time picker for the target day
    setTimePicker({ postId: active.id, dayIndex });
  };

  const handleTimePickerConfirm = (timeStr) => {
    if (!timePicker) return;
    const targetDate = addDays(weekStart, timePicker.dayIndex);
    moveMutation.mutate({
      id: timePicker.postId,
      date: formatDate(targetDate),
      time: timeStr,
    });
    setTimePicker(null);
  };

  const handleTimePickerCancel = () => {
    setTimePicker(null);
  };

  const handleDragCancel = () => {
    setActiveDragId(null);
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

  return (
    <div className="p-4 h-full overflow-auto">
      <DndContext
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        {/* 7-column grid */}
        <div className="grid grid-cols-7 gap-2 min-w-[900px]">
          {DAY_NAMES.map((dayName, dayIndex) => {
            const dayDate = addDays(weekStart, dayIndex);
            const dayIsToday = isToday(dayDate);
            const dayPosts = grid[dayIndex] || [];

            return (
              <div
                key={dayIndex}
                className={`rounded-xl overflow-hidden ${
                  dayIsToday ? 'bg-[#D4A853]/5 ring-1 ring-[#D4A853]/20' : 'bg-gray-50/50'
                }`}
              >
                {/* Day header */}
                <div
                  className={`px-3 py-2 text-center border-b ${
                    dayIsToday
                      ? 'bg-[#D4A853]/10 border-[#D4A853]/20'
                      : 'bg-white border-gray-200'
                  }`}
                >
                  <div className={`text-xs font-semibold uppercase tracking-wider ${
                    dayIsToday ? 'text-[#D4A853]' : 'text-[#2D4A3E]'
                  }`}>
                    {dayName}
                  </div>
                  <div className={`text-sm ${dayIsToday ? 'text-[#D4A853] font-bold' : 'text-gray-500'}`}>
                    {format(dayDate, 'M/d')}
                  </div>
                </div>

                {/* Droppable day column */}
                <div className="px-1.5 py-1">
                  <DroppableDay id={`day-${dayIndex}`}>
                    <div className="space-y-1.5">
                      {dayPosts.map((post) => (
                        <CalendarCard
                          key={post.id}
                          content={post}
                          isSelected={selectedPostId === post.id}
                          onSelect={handleSelect}
                          onAction={handleAction}
                          onTimeClick={(postId) => setTimePicker({ postId, dayIndex })}
                        />
                      ))}
                      {dayPosts.length === 0 && (
                        <div className="text-[10px] text-gray-300 text-center py-8">
                          Empty
                        </div>
                      )}
                    </div>
                  </DroppableDay>
                </div>
              </div>
            );
          })}
        </div>

        {/* Drag overlay */}
        <DragOverlay>
          {activeDragItem ? (
            <div className="opacity-80 w-[160px]">
              <CalendarCard
                content={activeDragItem}
                isSelected={false}
                onSelect={() => {}}
                onAction={() => {}}
              />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Time picker modal */}
      {timePicker && (
        <TimePickerModal
          dayDate={addDays(weekStart, timePicker.dayIndex)}
          onConfirm={handleTimePickerConfirm}
          onCancel={handleTimePickerCancel}
        />
      )}

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

      {/* Detail panel */}
      {detailContent && (
        <PostDetailPanel
          content={detailContent}
          onClose={() => setDetailContent(null)}
          onAction={handleAction}
          onRegenerated={invalidateCalendar}
        />
      )}
    </div>
  );
}
