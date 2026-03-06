import { useState, useEffect, useCallback } from 'react';
import { Check, X, Copy, ChevronDown, ChevronUp, Clock, Image as ImageIcon, ChevronLeft, ChevronRight, ZoomIn, Play, Send } from 'lucide-react';
import { format } from 'date-fns';

const STATUS_BADGE = {
  pending: 'badge-pending',
  approved: 'badge-approved',
  posted: 'badge-posted',
  rejected: 'badge-rejected',
};

const TYPE_LABELS = {
  daily_verse: 'Daily Verse',
  marriage_monday: 'Marriage Monday',
  parenting_wednesday: 'Parenting Wednesday',
  faith_friday: 'Faith Friday',
  encouragement: 'Encouragement',
  prayer_prompt: 'Prayer Prompt',
  gratitude: 'Gratitude',
  fill_in_blank: 'Fill in Blank',
  this_or_that: 'This or That',
  conviction_quote: 'Conviction Quote',
  parenting_list: 'Parenting List',
  marriage_challenge: 'Marriage Challenge',
  carousel: 'Carousel',
  reel: 'Reel',
};

export default function ContentCard({
  content,
  selected,
  onToggleSelect,
  onApprove,
  onReject,
  onPostNow,
  isApproving,
  isRejecting,
  isPosting,
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState('');
  const [lightboxIndex, setLightboxIndex] = useState(-1);

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(''), 1500);
  };

  const feedImage = content.images?.find((img) => img.format === 'feed_4x5');
  const allImages = content.images || [];

  return (
    <div className={`card transition-all ${selected ? 'ring-2 ring-brand-gold' : ''}`}>
      {/* Header Row */}
      <div className="flex items-start gap-4">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggleSelect}
          className="mt-1 accent-brand-gold"
        />

        {/* Thumbnail — click to open lightbox */}
        {feedImage?.final_url ? (
          <button
            onClick={() => setLightboxIndex(allImages.indexOf(feedImage))}
            className="relative group flex-shrink-0 rounded-lg overflow-hidden"
          >
            <img
              src={feedImage.final_url}
              alt={content.hook || 'Content image'}
              className="w-20 h-24 object-cover"
              onError={(e) => { e.target.parentElement.style.display = 'none'; }}
            />
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
              <ZoomIn size={18} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </button>
        ) : null}

        <div className="flex-1 min-w-0">
          {/* Type + Status Badges */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="badge bg-brand-cream text-brand-green text-xs">
              {TYPE_LABELS[content.content_type] || content.content_type}
            </span>
            <span className={STATUS_BADGE[content.status] || 'badge'}>
              {content.status}
            </span>
            {content.emotional_tone && (
              <span className="badge bg-gray-100 text-gray-600">
                {content.emotional_tone}
              </span>
            )}
            {content.scheduled_at && (
              <span className="text-xs text-gray-400 flex items-center gap-1 ml-auto">
                <Clock size={12} />
                {format(new Date(content.scheduled_at), 'MMM d, h:mm a')}
              </span>
            )}
          </div>

          {/* Platform Status */}
          {content.posting_status && Object.keys(content.posting_status).length > 0 && (
            <div className="flex items-center gap-2 mt-1">
              {['instagram', 'facebook', 'tiktok'].map((p) => {
                const ps = content.posting_status?.[p];
                if (!ps) return null;
                const icon = ps.status === 'success' ? '\u2713' : ps.status === 'failed' ? '\u2717' : '\u2013';
                const color = ps.status === 'success' ? 'text-green-600' : ps.status === 'failed' ? 'text-red-600' : 'text-gray-400';
                return (
                  <span key={p} className={`text-xs font-medium ${color}`} title={`${p}: ${ps.status}`}>
                    {p.charAt(0).toUpperCase()}{icon}
                  </span>
                );
              })}
            </div>
          )}

          {/* Hook */}
          <p className="font-semibold text-brand-green text-lg leading-snug">
            {content.hook || 'No hook generated'}
          </p>

          {/* Short Caption */}
          <p className="text-sm text-gray-600 mt-2">{content.caption_short}</p>

          {/* Caption Variants (expandable) */}
          {expanded && (
            <div className="mt-4 space-y-3 border-t pt-4">
              <CaptionBlock
                label="Medium Caption"
                text={content.caption_medium}
                onCopy={copyToClipboard}
                copied={copied}
              />
              <CaptionBlock
                label="Long Caption"
                text={content.caption_long}
                onCopy={copyToClipboard}
                copied={copied}
              />
              <CaptionBlock
                label="Story Text"
                text={content.story_text}
                onCopy={copyToClipboard}
                copied={copied}
              />
              <CaptionBlock
                label="Facebook"
                text={content.facebook_variation}
                onCopy={copyToClipboard}
                copied={copied}
              />
              <CaptionBlock
                label="15s Reel Script"
                text={content.reel_script_15}
                onCopy={copyToClipboard}
                copied={copied}
              />

              {/* Hashtag Tiers */}
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Hashtags</h4>
                <HashtagTier label="Large" tags={content.hashtags_large} onCopy={copyToClipboard} copied={copied} />
                <HashtagTier label="Medium" tags={content.hashtags_medium} onCopy={copyToClipboard} copied={copied} />
                <HashtagTier label="Niche" tags={content.hashtags_niche} onCopy={copyToClipboard} copied={copied} />
              </div>

              {/* Image Prompt */}
              {content.image_prompt && (
                <div className="mt-3">
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Image Prompt</h4>
                  <p className="text-xs text-gray-500 bg-gray-50 p-2 rounded">{content.image_prompt}</p>
                </div>
              )}

              {/* All Image Formats */}
              {allImages.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    <ImageIcon size={12} className="inline mr-1" />
                    Generated Images ({allImages.length})
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {allImages.map((img, idx) => (
                      <div key={img.id}>
                        {img.final_url ? (
                          <button
                            onClick={() => setLightboxIndex(idx)}
                            className="relative group w-full rounded-lg overflow-hidden border"
                          >
                            {img.format === 'reel_9x16' ? (
                              <div className="w-full h-32 bg-gray-900 flex items-center justify-center">
                                <Play size={28} className="text-white/70" />
                              </div>
                            ) : (
                              <img
                                src={img.final_url}
                                alt={img.format || 'Image'}
                                className="w-full h-32 object-cover"
                                onError={(e) => {
                                  e.target.parentElement.innerHTML =
                                    '<div class="w-full h-32 bg-gray-100 flex items-center justify-center text-xs text-gray-400">Failed to load</div>';
                                }}
                              />
                            )}
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                              {img.format === 'reel_9x16' ? (
                                <Play size={18} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                              ) : (
                                <ZoomIn size={18} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                              )}
                            </div>
                          </button>
                        ) : (
                          <div className="w-full h-32 bg-gray-100 rounded-lg border flex items-center justify-center text-xs text-gray-400">
                            No file
                          </div>
                        )}
                        <div className="mt-1 flex items-center gap-1">
                          <span className="text-xs text-gray-500">{img.format || 'unknown'}</span>
                          {img.provider && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-brand-cream text-brand-green">
                              {img.provider}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Image Lightbox */}
      {lightboxIndex >= 0 && allImages.length > 0 && (
        <ImageLightbox
          images={allImages}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(-1)}
          onNavigate={setLightboxIndex}
        />
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-gray-500 hover:text-brand-green flex items-center gap-1"
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {expanded ? 'Less' : 'More'}
        </button>

        <div className="ml-auto flex gap-2">
          {content.status === 'pending' && (
            <>
              <button
                onClick={onReject}
                disabled={isRejecting}
                className="flex items-center gap-1 px-3 py-1.5 text-sm border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition-colors"
              >
                <X size={14} /> Reject
              </button>
              <button
                onClick={onApprove}
                disabled={isApproving}
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-brand-green text-white rounded-lg hover:bg-brand-green-light transition-colors"
              >
                <Check size={14} /> Approve
              </button>
            </>
          )}
          {(content.status === 'pending' || content.status === 'approved') && (
            <button
              onClick={onPostNow}
              disabled={isPosting}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-brand-gold text-white rounded-lg hover:bg-brand-gold/90 disabled:opacity-50 transition-colors"
            >
              <Send size={14} />
              {isPosting ? 'Posting...' : 'Post Now'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CaptionBlock({ label, text, onCopy, copied }) {
  if (!text) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold text-gray-500 uppercase">{label}</span>
        <button
          onClick={() => onCopy(text, label)}
          className="text-xs text-brand-gold hover:text-brand-gold-dark flex items-center gap-1"
        >
          <Copy size={10} />
          {copied === label ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm text-gray-700 bg-gray-50 p-2 rounded">{text}</p>
    </div>
  );
}

function HashtagTier({ label, tags, onCopy, copied }) {
  if (!tags || tags.length === 0) return null;

  const tagString = tags.join(' ');
  const copyLabel = `hashtags-${label}`;

  return (
    <div className="mb-2">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-gray-400">{label}:</span>
        <button
          onClick={() => onCopy(tagString, copyLabel)}
          className="text-xs text-brand-gold hover:text-brand-gold-dark"
        >
          {copied === copyLabel ? 'Copied!' : 'Copy all'}
        </button>
      </div>
      <p className="text-xs text-blue-600">{tagString}</p>
    </div>
  );
}

const FORMAT_LABELS = {
  feed_4x5: 'Feed (4:5)',
  feed_1x1: 'Feed (1:1)',
  story_9x16: 'Story (9:16)',
  reel_9x16: 'Reel (9:16)',
};

function ImageLightbox({ images, index, onClose, onNavigate }) {
  const img = images[index];
  const hasPrev = index > 0;
  const hasNext = index < images.length - 1;

  const handleKey = useCallback(
    (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && hasPrev) onNavigate(index - 1);
      if (e.key === 'ArrowRight' && hasNext) onNavigate(index + 1);
    },
    [onClose, onNavigate, index, hasPrev, hasNext],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <div
        className="relative max-w-[90vw] max-h-[90vh] flex flex-col items-center"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 z-10 bg-white rounded-full p-1.5 shadow-lg hover:bg-gray-100 transition-colors"
        >
          <X size={18} />
        </button>

        {/* Image or Video */}
        {img.format === 'reel_9x16' ? (
          <video
            src={img.final_url}
            controls
            autoPlay
            loop
            className="max-w-[90vw] max-h-[80vh] object-contain rounded-lg"
          />
        ) : (
          <img
            src={img.final_url}
            alt={img.format || 'Full size'}
            className="max-w-[90vw] max-h-[80vh] object-contain rounded-lg"
          />
        )}

        {/* Caption bar */}
        <div className="flex items-center gap-3 mt-3 text-white text-sm">
          {img.provider && (
            <span className="px-2 py-0.5 rounded bg-brand-gold/80 text-white text-xs">
              {img.provider}
            </span>
          )}
          <span>{FORMAT_LABELS[img.format] || img.format}</span>
          <span className="text-white/50">
            {index + 1} / {images.length}
          </span>
        </div>

        {/* Navigation arrows */}
        {hasPrev && (
          <button
            onClick={() => onNavigate(index - 1)}
            className="absolute left-[-48px] top-1/2 -translate-y-1/2 bg-white/20 hover:bg-white/40 rounded-full p-2 transition-colors"
          >
            <ChevronLeft size={24} className="text-white" />
          </button>
        )}
        {hasNext && (
          <button
            onClick={() => onNavigate(index + 1)}
            className="absolute right-[-48px] top-1/2 -translate-y-1/2 bg-white/20 hover:bg-white/40 rounded-full p-2 transition-colors"
          >
            <ChevronRight size={24} className="text-white" />
          </button>
        )}
      </div>
    </div>
  );
}
