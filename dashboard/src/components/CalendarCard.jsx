import { useState, useRef, useEffect } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { MoreVertical, Play, GripVertical, Clock } from 'lucide-react';
import { parseISO } from 'date-fns';

const TYPE_COLORS = {
  daily_verse: 'bg-blue-100 text-blue-700',
  marriage_monday: 'bg-pink-100 text-pink-700',
  parenting_wednesday: 'bg-purple-100 text-purple-700',
  faith_friday: 'bg-emerald-100 text-emerald-700',
  encouragement: 'bg-amber-100 text-amber-700',
  prayer_prompt: 'bg-indigo-100 text-indigo-700',
  gratitude: 'bg-lime-100 text-lime-700',
  carousel: 'bg-cyan-100 text-cyan-700',
  reel: 'bg-rose-100 text-rose-700',
  christian_quote: 'bg-orange-100 text-orange-700',
  this_or_that: 'bg-violet-100 text-violet-700',
  fill_in_blank: 'bg-teal-100 text-teal-700',
};

const TYPE_LABELS = {
  daily_verse: 'Verse',
  marriage_monday: 'Marriage',
  parenting_wednesday: 'Parenting',
  faith_friday: 'Faith',
  encouragement: 'Encourage',
  prayer_prompt: 'Prayer',
  gratitude: 'Gratitude',
  carousel: 'Carousel',
  reel: 'Reel',
  christian_quote: 'Quote',
  this_or_that: 'This/That',
  fill_in_blank: 'Fill In',
};

const STATUS_COLORS = {
  pending: 'bg-amber-500',
  approved: 'bg-emerald-500',
  posted: 'bg-blue-500',
  rejected: 'bg-red-500',
};

const MENU_ACTIONS = [
  { key: 'post-now', label: 'Post Now' },
  { key: 'approve', label: 'Approve' },
  { key: 'reject', label: 'Reject' },
  { key: 'delete', label: 'Delete' },
  { key: 'ai-image', label: 'AI Image' },
  { key: 'view-details', label: 'View Details' },
];

export default function CalendarCard({ content, isSelected, onSelect, onAction, onTimeClick }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: content.id,
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const feedImage = content.images?.find((img) => img.format === 'feed_4x5');
  const hasReel = content.images?.some((img) => img.format === 'reel_9x16');
  const provider = content.images?.[0]?.provider;

  const isCarousel = content.content_type === 'carousel';
  const typeColor = TYPE_COLORS[content.content_type] || 'bg-gray-100 text-gray-700';
  const typeLabel = TYPE_LABELS[content.content_type] || content.content_type;
  const statusColor = STATUS_COLORS[content.status] || 'bg-gray-400';

  const handleMenuAction = (action) => {
    setMenuOpen(false);
    onAction(action, content.id);
  };

  // Carousel placeholder card
  if (isCarousel && content.status === 'pending' && !content.hook) {
    return (
      <div
        ref={setNodeRef}
        style={style}
        {...attributes}
        {...listeners}
        className="rounded-xl bg-cyan-50 border-2 border-dashed border-cyan-300 p-4 text-center cursor-grab"
      >
        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-cyan-100 text-cyan-700">
          Carousel
        </span>
        <p className="text-xs text-cyan-600 mt-2 font-medium">Design Coming Soon</p>
        <p className="text-[10px] text-cyan-400 mt-1">Wed &amp; Sat slots</p>
      </div>
    );
  }

  // Find any image for thumbnail (reel or feed)
  const anyImage = content.images?.find((img) => img.final_url);

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className={`
        rounded-xl bg-white p-2.5 transition-all
        ${isSelected ? 'border-l-4 border-[#D4A853] bg-[#FFF8F0]/50' : 'border border-gray-200'}
        ${isDragging ? 'opacity-50 shadow-lg scale-105' : 'shadow-sm hover:shadow-md'}
      `}
    >
      {/* Header row */}
      <div className="flex items-center gap-1.5 mb-2">
        {/* Drag handle - ONLY this triggers drag */}
        <div {...listeners} className="cursor-grab active:cursor-grabbing text-gray-300 hover:text-gray-500 flex-shrink-0">
          <GripVertical size={14} />
        </div>

        {/* Radio button */}
        <button
          onClick={() => onSelect(content.id)}
          className="flex-shrink-0"
        >
          <div
            className={`w-4 h-4 rounded-full border-2 flex items-center justify-center
              ${isSelected ? 'border-[#D4A853]' : 'border-gray-300 hover:border-gray-400'}`}
          >
            {isSelected && <div className="w-2 h-2 rounded-full bg-[#D4A853]" />}
          </div>
        </button>

        {/* Type badge */}
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${typeColor}`}>
          {typeLabel}
        </span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Kebab menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((prev) => !prev)}
            className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
          >
            <MoreVertical size={14} />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50 min-w-[120px]">
              {MENU_ACTIONS.map((action) => (
                <button
                  key={action.key}
                  onClick={() => handleMenuAction(action.key)}
                  className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-[#FFF8F0] transition-colors
                    ${action.key === 'delete' ? 'text-red-600' : 'text-gray-700'}`}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Content row: thumbnail + hook -- clickable for details */}
      <div
        className="flex gap-2 cursor-pointer"
        onClick={() => onAction('view-details', content.id)}
      >
        {/* Thumbnail */}
        <div className="flex-shrink-0 w-[60px] h-[80px] rounded-lg overflow-hidden bg-gray-100 relative">
          {(anyImage?.final_url || feedImage?.final_url) ? (
            <img
              src={anyImage?.final_url || feedImage?.final_url}
              alt=""
              className="w-full h-full object-cover"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-300 text-[10px]">
              No img
            </div>
          )}
          {hasReel && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/20">
              <Play size={16} className="text-white fill-white" />
            </div>
          )}
        </div>

        {/* Hook text */}
        <p className="text-xs text-[#2D4A3E] leading-snug line-clamp-3 flex-1 min-w-0">
          {content.hook || 'No hook'}
        </p>
      </div>

      {/* Footer row: time + status + provider */}
      <div className="flex items-center gap-2 mt-2">
        {content.scheduled_at && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (onTimeClick) onTimeClick(content.id);
            }}
            className="flex items-center gap-0.5 text-[10px] text-[#D4A853] font-medium hover:text-[#b8903a] hover:underline transition-colors"
            title="Click to change time"
          >
            <Clock size={10} />
            {(() => {
              const d = parseISO(content.scheduled_at);
              const h = d.getHours();
              const m = String(d.getMinutes()).padStart(2, '0');
              const period = h >= 12 ? 'PM' : 'AM';
              const h12 = h % 12 || 12;
              return `${h12}:${m} ${period}`;
            })()}
          </button>
        )}
        <span className={`w-2 h-2 rounded-full ${statusColor}`} />
        <span className="text-[10px] text-gray-500 capitalize">{content.status}</span>
        <div className="flex-1" />
      </div>
    </div>
  );
}
