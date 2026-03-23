import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  Sparkles,
  Image as ImageIcon,
  Search,
  Mic,
  MicOff,
  Film,
  Send,
  CalendarPlus,
  CheckCircle,
  Loader2,
  Minus,
  Plus,
} from 'lucide-react';

import ImageLibrary from '../components/ImageLibrary.jsx';
import PhonePreview from '../components/PhonePreview.jsx';
import { createPost, postNow, rescheduleContent, fetchContentDetail, generateText } from '../lib/api.js';

const CONTENT_TYPES = [
  { value: 'daily_verse', label: 'Daily Verse' },
  { value: 'encouragement', label: 'Encouragement' },
  { value: 'marriage_monday', label: 'Marriage Monday' },
  { value: 'faith_friday', label: 'Faith Friday' },
  { value: 'christian_quote', label: 'Christian Quote' },
  { value: 'carousel', label: 'Carousel' },
];

const REEL_STYLES = [
  { value: 'classic', label: 'Classic' },
  { value: 'quick', label: 'Quick' },
  { value: 'cinematic', label: 'Cinematic' },
];

const IMAGE_SOURCES = [
  { value: 'library', label: 'Library', icon: ImageIcon },
  { value: 'ai', label: 'AI Generate', icon: Sparkles },
  { value: 'unsplash', label: 'Unsplash', icon: Search },
];

const FONT_FAMILIES = [
  { value: 'georgia', label: 'Georgia', css: 'Georgia, serif' },
  { value: 'playfair', label: 'Playfair', css: '"Playfair Display", Georgia, serif' },
  { value: 'lato', label: 'Lato', css: 'Lato, sans-serif' },
  { value: 'calibri', label: 'Calibri', css: 'Calibri, sans-serif' },
];

const COLOR_SWATCHES = [
  { value: '#FFFFFF', label: 'White', tw: 'bg-white border border-gray-300' },
  { value: '#FFF8F0', label: 'Cream', tw: 'bg-[#FFF8F0] border border-gray-200' },
  { value: '#D4A853', label: 'Gold', tw: 'bg-[#D4A853]' },
  { value: '#2D4A3E', label: 'Green', tw: 'bg-[#2D4A3E]' },
  { value: '#000000', label: 'Black', tw: 'bg-black' },
];

export default function CreatorPage() {
  const queryClient = useQueryClient();
  // Form state
  const [contentType, setContentType] = useState('daily_verse');
  const [text, setText] = useState('');
  const [imageSource, setImageSource] = useState('library');
  const [selectedImage, setSelectedImage] = useState(null);
  const [aiImagePrompt, setAiImagePrompt] = useState('');
  const [unsplashQuery, setUnsplashQuery] = useState('');
  const [narrationEnabled, setNarrationEnabled] = useState(true);
  const [reelStyle, setReelStyle] = useState('classic');
  const [fontSize, setFontSize] = useState(18); // preview font size (maps to reel font)
  const [fontFamily, setFontFamily] = useState('georgia');
  const [textColor, setTextColor] = useState('#FFFFFF');
  const [aiGenerating, setAiGenerating] = useState(false);

  // Post-creation state
  const [createdContentId, setCreatedContentId] = useState(null);
  const [createdContent, setCreatedContent] = useState(null);
  const [showScheduler, setShowScheduler] = useState(false);
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleSlot, setScheduleSlot] = useState('morning');

  // Mutations
  const createMutation = useMutation({
    mutationFn: createPost,
    onSuccess: async (data) => {
      const contentId = data.id || data.content_id;
      setCreatedContentId(contentId);
      queryClient.invalidateQueries({ queryKey: ['calendar'] });

      // Fetch full content detail to get images and reel URL
      try {
        const detail = await fetchContentDetail(contentId);
        setCreatedContent(detail);
      } catch {
        // Detail fetch failed, still show action buttons
      }
    },
  });

  const postNowMutation = useMutation({
    mutationFn: () => postNow(createdContentId),
  });

  const scheduleMutation = useMutation({
    mutationFn: () => {
      const timeMap = { morning: '06:30:00', noon: '12:00:00' };
      const scheduledAt = `${scheduleDate}T${timeMap[scheduleSlot]}`;
      return rescheduleContent(createdContentId, scheduledAt);
    },
    onSuccess: () => {
      setShowScheduler(false);
    },
  });

  const handleCreateReel = () => {
    // Map preview font size (10-28px in phone) to reel font size (24-80px at 1080p)
    const reelFontSize = Math.round(fontSize * (50 / 18));
    const payload = {
      content_type: contentType,
      text,
      image_source: imageSource,
      image_id: selectedImage?.id || null,
      ai_prompt: imageSource === 'ai' ? aiImagePrompt : null,
      unsplash_query: imageSource === 'unsplash' ? unsplashQuery : null,
      narration: narrationEnabled,
      reel_style: reelStyle,
      overlay_style: 'creator',
      font_size: reelFontSize,
      font_family: fontFamily,
      text_color: textColor,
    };
    setCreatedContent(null);
    setCreatedContentId(null);
    createMutation.mutate(payload);
  };

  const handleReset = () => {
    setText('');
    setSelectedImage(null);
    setAiImagePrompt('');
    setCreatedContentId(null);
    setCreatedContent(null);
    setShowScheduler(false);
    createMutation.reset();
    postNowMutation.reset();
    scheduleMutation.reset();
  };

  const getPreviewImageUrl = () => {
    if (!selectedImage) return null;
    if (selectedImage.final_url) return selectedImage.final_url;
    if (selectedImage.filename) return `/static/library/${selectedImage.filename}`;
    return null;
  };

  // Get reel URL from created content
  const getCreatedReelUrl = () => {
    if (!createdContent?.images) return null;
    const reel = createdContent.images.find((img) => img.format === 'reel_9x16');
    return reel?.final_url || null;
  };

  // Get any feed image from created content for preview
  const getCreatedImageUrl = () => {
    if (!createdContent?.images) return null;
    const feed = createdContent.images.find((img) => img.format === 'feed_4x5');
    if (feed?.final_url) return feed.final_url;
    const any = createdContent.images.find((img) => img.final_url);
    return any?.final_url || null;
  };

  const reelUrl = getCreatedReelUrl();
  const createdImageUrl = getCreatedImageUrl();

  return (
    <div className="flex gap-6 h-full">
      {/* LEFT PANEL -- Editor */}
      <div className="w-3/5 overflow-y-auto pr-4 space-y-5">
        <h1 className="font-heading text-2xl text-brand-green">Create Post</h1>

        {/* Content Type */}
        <div>
          <label className="block text-sm font-body text-gray-600 mb-1">Content Type</label>
          <div className="relative">
            <select
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              className="w-full appearance-none bg-white border border-gray-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-body focus:outline-none focus:ring-2 focus:ring-brand-gold/40 focus:border-brand-gold"
            >
              {CONTENT_TYPES.map((ct) => (
                <option key={ct.value} value={ct.value}>
                  {ct.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Your Text */}
        <div>
          <label className="block text-sm font-body text-gray-600 mb-1">Your Text</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder="Enter your verse, quote, or caption..."
            className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm font-body resize-none focus:outline-none focus:ring-2 focus:ring-brand-gold/40 focus:border-brand-gold"
          />
          <button
            onClick={async () => {
              setAiGenerating(true);
              try {
                const data = await generateText(contentType);
                setText(data.text);
              } catch (err) {
                // Fallback if API is unavailable
                setText('Be still and know that I am God. - Psalm 46:10');
              } finally {
                setAiGenerating(false);
              }
            }}
            disabled={aiGenerating}
            className="mt-2 flex items-center gap-1.5 px-4 py-2 border border-brand-green text-brand-green text-sm font-body rounded-lg hover:bg-brand-green/5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {aiGenerating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            {aiGenerating ? 'Generating...' : 'Generate with AI'}
          </button>
        </div>

        {/* Text Size */}
        <div className="flex items-center justify-between bg-white rounded-xl border border-gray-100 px-4 py-3">
          <span className="text-sm font-body text-gray-700">Text Size</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setFontSize((s) => Math.max(10, s - 2))}
              className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 transition-colors"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <input
              type="range"
              min={10}
              max={28}
              step={1}
              value={fontSize}
              onChange={(e) => setFontSize(Number(e.target.value))}
              className="w-24 accent-brand-gold"
            />
            <button
              onClick={() => setFontSize((s) => Math.min(28, s + 2))}
              className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
            <span className="text-xs text-gray-400 w-8 text-right">{fontSize}px</span>
          </div>
        </div>

        {/* Font Family */}
        <div className="bg-white rounded-xl border border-gray-100 px-4 py-3">
          <span className="text-sm font-body text-gray-700 block mb-2">Font Family</span>
          <div className="flex gap-2">
            {FONT_FAMILIES.map((f) => (
              <button
                key={f.value}
                onClick={() => setFontFamily(f.value)}
                className={`flex-1 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  fontFamily === f.value
                    ? 'border-brand-gold bg-brand-gold/10 text-brand-gold'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
                style={{ fontFamily: f.css }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Text Color */}
        <div className="bg-white rounded-xl border border-gray-100 px-4 py-3">
          <span className="text-sm font-body text-gray-700 block mb-2">Text Color</span>
          <div className="flex gap-3 items-center">
            {COLOR_SWATCHES.map((c) => (
              <button
                key={c.value}
                onClick={() => setTextColor(c.value)}
                title={c.label}
                className={`w-8 h-8 rounded-full ${c.tw} transition-all ${
                  textColor === c.value
                    ? 'ring-2 ring-brand-gold ring-offset-2'
                    : 'hover:scale-110'
                }`}
              />
            ))}
            <span className="text-xs text-gray-400 ml-1">{textColor}</span>
          </div>
        </div>

        {/* Image Source */}
        <div>
          <label className="block text-sm font-body text-gray-600 mb-2">Image Source</label>
          <div className="flex gap-2 mb-3">
            {IMAGE_SOURCES.map((source) => {
              const Icon = source.icon;
              return (
                <button
                  key={source.value}
                  onClick={() => setImageSource(source.value)}
                  className={`flex items-center gap-1.5 px-4 py-2 text-sm font-body rounded-lg border transition-colors ${
                    imageSource === source.value
                      ? 'border-brand-gold bg-brand-gold/10 text-brand-gold'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {source.label}
                </button>
              );
            })}
          </div>

          {/* Image source content */}
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            {imageSource === 'library' && (
              <ImageLibrary onSelect={setSelectedImage} />
            )}

            {imageSource === 'ai' && (
              <div className="space-y-3">
                <textarea
                  value={aiImagePrompt}
                  onChange={(e) => setAiImagePrompt(e.target.value)}
                  rows={3}
                  placeholder="Describe the image you want to generate..."
                  className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-body resize-none focus:outline-none focus:ring-2 focus:ring-purple-300"
                />
                <p className="text-xs text-gray-500 font-body">
                  AI image will be generated via fal.ai when you click "Create Reel" below.
                  The prompt will be used to create a custom background image for your reel.
                </p>
                {aiImagePrompt.trim() && (
                  <div className="flex items-center gap-2 p-2 bg-purple-50 rounded-lg">
                    <CheckCircle className="w-4 h-4 text-purple-600 flex-shrink-0" />
                    <span className="text-xs text-purple-700 font-body">
                      Prompt ready: "{aiImagePrompt.length > 60 ? aiImagePrompt.slice(0, 60) + '...' : aiImagePrompt}"
                    </span>
                  </div>
                )}
              </div>
            )}

            {imageSource === 'unsplash' && (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={unsplashQuery}
                    onChange={(e) => setUnsplashQuery(e.target.value)}
                    placeholder="Search Unsplash photos..."
                    className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:ring-2 focus:ring-brand-gold/40"
                  />
                  <button className="flex items-center gap-1 px-4 py-2 bg-brand-green text-white text-sm font-body rounded-lg hover:bg-brand-green-light transition-colors">
                    <Search className="w-3.5 h-3.5" />
                    Search
                  </button>
                </div>
                <p className="text-xs text-gray-500 font-body">
                  Unsplash images are automatically fetched when you click "Create Reel".
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Selected image preview */}
        {selectedImage && imageSource === 'library' && (
          <div className="flex items-center gap-3 bg-white rounded-xl border border-gray-100 p-3">
            <img
              src={getPreviewImageUrl()}
              alt=""
              className="w-12 h-12 rounded-lg object-cover"
            />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-body text-gray-700 truncate">
                {selectedImage.prompt_or_query || selectedImage.filename || 'Library image selected'}
              </p>
              <p className="text-[10px] text-gray-400 uppercase">{selectedImage.provider || 'library'}</p>
            </div>
            <button
              onClick={() => setSelectedImage(null)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Clear
            </button>
          </div>
        )}

        {/* Narration toggle */}
        <div className="flex items-center justify-between bg-white rounded-xl border border-gray-100 px-4 py-3">
          <div className="flex items-center gap-2">
            {narrationEnabled ? (
              <Mic className="w-4 h-4 text-brand-gold" />
            ) : (
              <MicOff className="w-4 h-4 text-gray-400" />
            )}
            <span className="text-sm font-body text-gray-700">Narration</span>
          </div>
          <button
            onClick={() => setNarrationEnabled((prev) => !prev)}
            className="relative"
          >
            <div
              className={`w-10 h-5 rounded-full transition-colors ${
                narrationEnabled ? 'bg-brand-gold' : 'bg-gray-300'
              }`}
            />
            <div
              className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                narrationEnabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        {/* Reel Style */}
        <div>
          <label className="block text-sm font-body text-gray-600 mb-1">Reel Style</label>
          <div className="relative">
            <select
              value={reelStyle}
              onChange={(e) => setReelStyle(e.target.value)}
              className="w-full appearance-none bg-white border border-gray-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-body focus:outline-none focus:ring-2 focus:ring-brand-gold/40 focus:border-brand-gold"
            >
              {REEL_STYLES.map((style) => (
                <option key={style.value} value={style.value}>
                  {style.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Create Reel button */}
        <button
          onClick={handleCreateReel}
          disabled={!text.trim() || createMutation.isPending}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-brand-gold text-white text-base font-heading rounded-xl hover:bg-brand-gold-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-md"
        >
          {createMutation.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Film className="w-5 h-5" />
          )}
          {createMutation.isPending ? 'Creating Reel...' : 'Create Reel'}
        </button>

        {createMutation.isError && (
          <p className="text-red-500 text-sm font-body">
            {createMutation.error?.message || 'Failed to create post. Please try again.'}
          </p>
        )}

        {createMutation.isSuccess && (
          <p className="text-green-600 text-sm font-body flex items-center gap-1.5">
            <CheckCircle className="w-4 h-4" />
            Reel created successfully! (ID: {createdContentId})
          </p>
        )}
      </div>

      {/* RIGHT PANEL -- Preview */}
      <div className="w-2/5 space-y-4">
        {/* Show reel video if created, otherwise phone preview */}
        {reelUrl ? (
          <div className="space-y-3">
            <h3 className="font-heading text-lg text-brand-green">Reel Preview</h3>
            <div className="rounded-2xl overflow-hidden bg-black shadow-lg" style={{ maxWidth: 280 }}>
              <video
                src={reelUrl}
                controls
                className="w-full"
                style={{ maxHeight: 500 }}
              />
            </div>
            <p className="text-xs text-gray-500 font-body">
              {createdContent?.images?.length || 0} images generated
            </p>
          </div>
        ) : (
          <PhonePreview
            text={text}
            imageUrl={createdImageUrl || getPreviewImageUrl()}
            contentType={contentType}
            fontSize={fontSize}
            fontFamily={fontFamily}
            textColor={textColor}
          />
        )}

        {/* Post-creation actions */}
        {createdContentId && (
          <div className="space-y-2 mt-4">
            <button
              onClick={() => postNowMutation.mutate()}
              disabled={postNowMutation.isPending || postNowMutation.isSuccess}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-gold text-white text-sm font-body rounded-xl hover:bg-brand-gold-dark disabled:opacity-50 transition-colors"
            >
              <Send className="w-4 h-4" />
              {postNowMutation.isPending
                ? 'Posting...'
                : postNowMutation.isSuccess
                  ? 'Posted!'
                  : 'Post Now'}
            </button>

            <button
              onClick={() => setShowScheduler((prev) => !prev)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-brand-green text-brand-green text-sm font-body rounded-xl hover:bg-brand-green/5 transition-colors"
            >
              <CalendarPlus className="w-4 h-4" />
              Add to Schedule
            </button>

            <button
              onClick={handleReset}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-300 text-gray-500 text-sm font-body rounded-xl hover:bg-gray-50 transition-colors"
            >
              Create Another
            </button>

            {showScheduler && (
              <div className="bg-white rounded-xl border border-gray-100 p-4 space-y-3">
                <div>
                  <label className="block text-xs font-body text-gray-500 mb-1">Date</label>
                  <input
                    type="date"
                    value={scheduleDate}
                    onChange={(e) => setScheduleDate(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:ring-2 focus:ring-brand-gold/40"
                  />
                </div>
                <div>
                  <label className="block text-xs font-body text-gray-500 mb-1">Time Slot</label>
                  <div className="flex gap-2">
                    {['morning', 'noon'].map((slot) => (
                      <button
                        key={slot}
                        onClick={() => setScheduleSlot(slot)}
                        className={`flex-1 px-3 py-2 text-sm font-body rounded-lg border transition-colors ${
                          scheduleSlot === slot
                            ? 'border-brand-gold bg-brand-gold/10 text-brand-gold'
                            : 'border-gray-200 text-gray-600 hover:border-gray-300'
                        }`}
                      >
                        {slot === 'morning' ? 'Morning (6:30 AM)' : 'Noon (12:00 PM)'}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => scheduleMutation.mutate()}
                  disabled={!scheduleDate || scheduleMutation.isPending}
                  className="w-full px-4 py-2 bg-brand-green text-white text-sm font-body rounded-lg hover:bg-brand-green-light disabled:opacity-50 transition-colors"
                >
                  {scheduleMutation.isPending ? 'Scheduling...' : 'Confirm Schedule'}
                </button>
                {scheduleMutation.isSuccess && (
                  <p className="text-brand-green text-xs font-body text-center">
                    Scheduled successfully!
                  </p>
                )}
              </div>
            )}

            {postNowMutation.isError && (
              <p className="text-red-500 text-xs font-body">
                {postNowMutation.error?.message || 'Failed to post.'}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
