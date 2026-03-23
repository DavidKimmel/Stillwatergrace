import { format } from 'date-fns';

const MEDIA_BADGE_COLORS = {
  VIDEO: 'bg-purple-100 text-purple-700',
  IMAGE: 'bg-blue-100 text-blue-700',
  CAROUSEL_ALBUM: 'bg-amber-100 text-amber-700',
};

function mediaBadgeLabel(type) {
  if (type === 'CAROUSEL_ALBUM') return 'CAROUSEL';
  return type || 'POST';
}

export default function CompetitorCard({ post, handle, onInspire }) {
  const badgeColor = MEDIA_BADGE_COLORS[post.media_type] || 'bg-gray-100 text-gray-700';
  const postedDate = post.posted_at
    ? format(new Date(post.posted_at), 'MMM d, yyyy')
    : 'Unknown';

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex flex-col gap-3">
      {/* Handle */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-brand-green/10 flex items-center justify-center text-brand-green text-xs font-bold">
          {(handle || '?')[0].toUpperCase()}
        </div>
        <span className="text-sm font-medium text-brand-green">@{handle}</span>
      </div>

      {/* Caption preview */}
      <p className="text-sm text-gray-700 line-clamp-3 leading-relaxed">
        {post.caption || post.caption_preview || 'No caption available'}
      </p>

      {/* Meta row */}
      <div className="flex items-center justify-between mt-auto">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeColor}`}>
            {mediaBadgeLabel(post.media_type)}
          </span>
          <span className="text-xs text-gray-400">{postedDate}</span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2 mt-1">
        {post.permalink && (
          <a
            href={post.permalink}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors"
          >
            View Post
          </a>
        )}
        {onInspire && (
          <button
            onClick={() => onInspire(post)}
            className="text-xs font-medium px-3 py-1.5 rounded-lg border border-brand-gold text-brand-gold hover:bg-brand-gold hover:text-white transition-colors"
          >
            Inspire
          </button>
        )}
      </div>
    </div>
  );
}
