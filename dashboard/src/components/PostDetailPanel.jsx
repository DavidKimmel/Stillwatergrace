import { X, Copy, Check, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { regenerateReel } from '../lib/api';

const REEL_PRESETS = [
  { value: '', label: 'Auto (based on content type)' },
  { value: 'stillwatergrace', label: 'StillwaterGrace (narrated)' },
  { value: 'encouragement', label: 'Encouragement (word pop)' },
  { value: 'verse_card', label: 'Verse Card (typography)' },
  { value: 'coffee_verse', label: 'Coffee Verse (morning devotional)' },
];

const VOICE_OPTIONS = [
  { value: '', label: 'Auto (random from pool)' },
  { value: 'VU16byTywsWv5JpI8rbc', label: 'Ash — Calm, Soothing' },
  { value: 'gUABw7pXQjhjt0kNFBTF', label: 'Andrew — Smooth, Clear' },
  { value: '3AvFKjwBVQoGCFjmz5ib', label: 'Suzanne — Casual, Female' },
  { value: 'oQV06a7Gn8pbCJh5DXcO', label: 'Archer — Clean, Balanced' },
  { value: 'uju3wxzG5OhpWcoi3SMy', label: 'Michael — Confident' },
  { value: 'jfIS2w2yJi0grJZPyEsk', label: 'Oliver Silk — British, Deep' },
  { value: 'B5jEZPqk2OJ2vkPw3wBM', label: 'Cillian — Irish, Calm' },
  { value: '66y97vsfcmXgLh93gcal', label: 'Connery — Intense' },
  { value: 'WrPknjKhmIXkCONEtG3j', label: 'Nick — Warm, Natural' },
];

const TYPE_LABELS = {
  daily_verse: 'Daily Verse',
  marriage_monday: 'Marriage Monday',
  parenting_wednesday: 'Parenting Wednesday',
  faith_friday: 'Faith Friday',
  encouragement: 'Encouragement',
  prayer_prompt: 'Prayer Prompt',
  gratitude: 'Gratitude',
  carousel: 'Carousel',
  reel: 'Reel',
  christian_quote: 'Christian Quote',
  this_or_that: 'This or That',
  fill_in_blank: 'Fill in Blank',
};

export default function PostDetailPanel({ content, onClose, onAction, onRegenerated }) {
  const [copied, setCopied] = useState('');
  const [selectedPreset, setSelectedPreset] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('');
  const [regenerating, setRegenerating] = useState(false);

  if (!content) return null;

  const copyText = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(''), 1500);
  };

  const handleRegenerateReel = async () => {
    setRegenerating(true);
    try {
      await regenerateReel(content.id, selectedPreset || undefined, selectedVoice || undefined);
      if (onRegenerated) onRegenerated();
    } catch (err) {
      console.error('Regenerate reel failed:', err);
    } finally {
      setRegenerating(false);
    }
  };

  // Prefer the AI (fal) reel over the original unsplash reel
  const reelImages = content.images?.filter((img) => img.format === 'reel_9x16') || [];
  const reelImage = reelImages.find((img) => img.provider === 'fal') || reelImages[0];
  const allImages = content.images || [];

  const hashtagGroups = [
    { label: 'Large', tags: content.hashtags_large },
    { label: 'Medium', tags: content.hashtags_medium },
    { label: 'Niche', tags: content.hashtags_niche },
  ];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white shadow-2xl overflow-y-auto animate-in slide-in-from-right duration-200">
        {/* Sticky header */}
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
          <h3 className="font-heading text-lg text-[#2D4A3E]">
            {TYPE_LABELS[content.content_type] || content.content_type}
          </h3>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize
            ${content.status === 'pending' ? 'bg-amber-100 text-amber-700' : ''}
            ${content.status === 'approved' ? 'bg-emerald-100 text-emerald-700' : ''}
            ${content.status === 'posted' ? 'bg-blue-100 text-blue-700' : ''}
            ${content.status === 'rejected' ? 'bg-red-100 text-red-700' : ''}
          `}>
            {content.status}
          </span>
          <span className="text-xs text-gray-400 ml-auto">ID: {content.id}</span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Panel body */}
        <div className="px-6 py-4">

      {/* Hook */}
      <div className="mb-4">
        <SectionLabel label="Hook" text={content.hook} onCopy={copyText} copied={copied} />
      </div>

      {/* Caption variants */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <CaptionBlock label="Short Caption" text={content.caption_short} onCopy={copyText} copied={copied} />
        <CaptionBlock label="Medium Caption" text={content.caption_medium} onCopy={copyText} copied={copied} />
        <CaptionBlock label="Long Caption" text={content.caption_long} onCopy={copyText} copied={copied} />
      </div>

      {/* Facebook + Reel script */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <CaptionBlock label="Facebook" text={content.facebook_variation} onCopy={copyText} copied={copied} />
        <CaptionBlock label="Reel Script" text={content.reel_script_15} onCopy={copyText} copied={copied} />
      </div>

      {/* Hashtags */}
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Hashtags</h4>
        <div className="space-y-1">
          {hashtagGroups.map((group) => {
            if (!group.tags?.length) return null;
            const tagStr = group.tags.join(' ');
            const copyKey = `hashtags-${group.label}`;
            return (
              <div key={group.label} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400 w-12">{group.label}:</span>
                <span className="text-xs text-blue-600 flex-1">{tagStr}</span>
                <button
                  onClick={() => copyText(tagStr, copyKey)}
                  className="text-[10px] text-[#D4A853] hover:text-[#b8903a]"
                >
                  {copied === copyKey ? 'Copied!' : 'Copy'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Reel video player */}
      {reelImage?.final_url && (
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Reel Preview</h4>
          <video
            src={reelImage.final_url}
            controls
            className="w-full max-w-sm rounded-lg border"
          />
        </div>
      )}

      {/* All images horizontal scroll */}
      {allImages.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
            Images ({allImages.length})
          </h4>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {allImages.map((img) => (
              <div key={img.id} className="flex-shrink-0">
                {img.final_url ? (
                  <img
                    src={img.final_url}
                    alt={img.format}
                    className="w-24 h-32 object-cover rounded-lg border"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="w-24 h-32 rounded-lg border bg-gray-50 flex items-center justify-center text-[10px] text-gray-400">
                    No file
                  </div>
                )}
                <div className="flex items-center gap-1 mt-1">
                  <span className="text-[10px] text-gray-500">{img.format}</span>
                  {img.provider && (
                    <span className="text-[9px] px-1 py-0.5 rounded bg-gray-100 text-gray-500 uppercase">
                      {img.provider === 'fal' ? 'AI' : img.provider}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reel style + voice selector */}
      <div className="mb-4 p-3 bg-gray-50 rounded-lg">
        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-3">Reel Settings</h4>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-[10px] text-gray-400 uppercase mb-1 block">Style</label>
            <select
              value={selectedPreset}
              onChange={(e) => setSelectedPreset(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-[#2D4A3E] focus:outline-none focus:ring-2 focus:ring-[#D4A853]/40"
            >
              {REEL_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-gray-400 uppercase mb-1 block">Voice</label>
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-[#2D4A3E] focus:outline-none focus:ring-2 focus:ring-[#D4A853]/40"
            >
              {VOICE_OPTIONS.map((v) => (
                <option key={v.value} value={v.value}>{v.label}</option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={handleRegenerateReel}
          disabled={regenerating}
          className={`w-full flex items-center justify-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors ${
            regenerating
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-[#2D4A3E] text-white hover:bg-[#2D4A3E]/90'
          }`}
        >
          <RefreshCw size={14} className={regenerating ? 'animate-spin' : ''} />
          {regenerating ? 'Rendering...' : 'Regenerate Reel'}
        </button>
      </div>

      {/* Action buttons — sticky at bottom */}
      <div className="flex flex-wrap items-center gap-2 pt-4 border-t">
        <button
          onClick={() => onAction('approve', content.id)}
          className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
        >
          Approve
        </button>
        <button
          onClick={() => onAction('reject', content.id)}
          className="px-4 py-2 text-sm font-medium bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
        >
          Reject
        </button>
        <button
          onClick={() => onAction('post-now', content.id)}
          className="px-4 py-2 text-sm font-medium bg-[#D4A853] text-white rounded-lg hover:bg-[#b8903a] transition-colors"
        >
          Post Now
        </button>
        <button
          onClick={() => onAction('ai-image', content.id)}
          className="px-4 py-2 text-sm font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          AI Image
        </button>
        <button
          onClick={() => onAction('swap-reel', content.id)}
          className="px-4 py-2 text-sm font-medium bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
        >
          Swap Reel
        </button>
      </div>

        </div>{/* end panel body */}
      </div>{/* end slide-over */}
    </>
  );
}

function SectionLabel({ label, text, onCopy, copied }) {
  if (!text) return null;
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-semibold text-gray-500 uppercase">{label}</span>
        <button
          onClick={() => onCopy(text, label)}
          className="text-[10px] text-[#D4A853] hover:text-[#b8903a] flex items-center gap-0.5"
        >
          {copied === label ? <Check size={10} /> : <Copy size={10} />}
          {copied === label ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm font-semibold text-[#2D4A3E]">{text}</p>
    </div>
  );
}

function CaptionBlock({ label, text, onCopy, copied }) {
  if (!text) return null;
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-semibold text-gray-500 uppercase">{label}</span>
        <button
          onClick={() => onCopy(text, label)}
          className="text-[10px] text-[#D4A853] hover:text-[#b8903a]"
        >
          {copied === label ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-xs text-gray-700 leading-relaxed">{text}</p>
    </div>
  );
}
