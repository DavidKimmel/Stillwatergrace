import { useState, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { format, addDays } from 'date-fns';

import { generateContent, fetchContentQueue } from '../lib/api';

export default function TopBar({ weekStart, onWeekChange }) {
  const queryClient = useQueryClient();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [scheduledCount, setScheduledCount] = useState(0);
  const dropdownRef = useRef(null);

  const weekEnd = addDays(weekStart, 6);
  const weekLabel = `${format(weekStart, 'MMM d')} - ${format(weekEnd, 'MMM d, yyyy')}`;

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Fetch counts
  useEffect(() => {
    const loadCounts = async () => {
      try {
        const pending = await fetchContentQueue({ status: 'pending' });
        const approved = await fetchContentQueue({ status: 'approved' });
        setPendingCount(pending?.total ?? (Array.isArray(pending) ? pending.length : 0));
        setScheduledCount(approved?.total ?? (Array.isArray(approved) ? approved.length : 0));
      } catch {
        // Mock fallback handles this
      }
    };
    loadCounts();
  }, [generating]);

  // Auto-clear toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const handleGenerate = async (days) => {
    setDropdownOpen(false);
    setGenerating(true);
    setToast(null);
    try {
      await generateContent(days);
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      setToast({ type: 'success', message: `Generated ${days} day${days > 1 ? 's' : ''} of content` });
    } catch (err) {
      setToast({ type: 'error', message: err.message || 'Generation failed' });
    } finally {
      setGenerating(false);
    }
  };

  const navigateWeek = (direction) => {
    onWeekChange(addDays(weekStart, direction * 7));
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
      {/* Week navigation */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => navigateWeek(-1)}
          className="p-1.5 rounded-md hover:bg-gray-100 text-brand-green transition-colors"
        >
          <ChevronLeft size={18} />
        </button>
        <span className="text-sm font-medium text-brand-green min-w-[180px] text-center">
          {weekLabel}
        </span>
        <button
          onClick={() => navigateWeek(1)}
          className="p-1.5 rounded-md hover:bg-gray-100 text-brand-green transition-colors"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Generate button */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen((prev) => !prev)}
          disabled={generating}
          className="flex items-center gap-2 bg-brand-gold text-white px-4 py-1.5 rounded-lg text-sm font-semibold hover:bg-brand-gold-dark transition-colors disabled:opacity-60"
        >
          {generating && <Loader2 size={14} className="animate-spin" />}
          Generate
        </button>

        {dropdownOpen && (
          <div className="absolute top-full mt-1 right-0 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50 min-w-[120px]">
            {[1, 2, 3, 4, 5, 6, 7].map((n) => (
              <button
                key={n}
                onClick={() => handleGenerate(n)}
                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-brand-cream transition-colors"
              >
                {n} day{n > 1 ? 's' : ''}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Stats + Toast */}
      <div className="flex items-center gap-3">
        {toast && (
          <span
            className={`text-xs px-3 py-1 rounded-full font-medium ${
              toast.type === 'success'
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            }`}
          >
            {toast.message}
          </span>
        )}
        <span className="badge-pending">{pendingCount} Pending</span>
        <span className="badge-approved">{scheduledCount} Scheduled</span>
      </div>
    </header>
  );
}
