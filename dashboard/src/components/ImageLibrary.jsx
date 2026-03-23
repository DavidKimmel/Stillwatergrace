import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';

import { getImageLibrary, generateAiImage } from '../lib/api.js';

const THEMES = ['Nature', 'People', 'Faith', 'Dramatic', 'Interactive', 'Botanical'];

export default function ImageLibrary({ onSelect }) {
  const [activeTheme, setActiveTheme] = useState('Nature');
  const [unusedOnly, setUnusedOnly] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const queryClient = useQueryClient();

  const { data: response, isLoading } = useQuery({
    queryKey: ['image-library', activeTheme, unusedOnly],
    queryFn: () =>
      getImageLibrary({
        theme: activeTheme.toLowerCase(),
        unused: unusedOnly ? 'true' : 'false',
      }),
    staleTime: 60_000,
  });

  const images = response?.images || response || [];

  const handleSelect = (image) => {
    setSelectedId(image.id);
    onSelect(image);
  };

  const getImageUrl = (image) => {
    if (image.final_url) return image.final_url;
    return `/static/library/${image.filename}`;
  };

  return (
    <div className="space-y-3">
      {/* Theme tabs + Unused toggle */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 flex-wrap">
          {THEMES.map((theme) => (
            <button
              key={theme}
              onClick={() => setActiveTheme(theme)}
              className={`px-3 py-1 text-xs font-body rounded-full transition-colors ${
                activeTheme === theme
                  ? 'bg-brand-gold text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {theme}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer whitespace-nowrap ml-2">
          <span>Unused</span>
          <div className="relative">
            <input
              type="checkbox"
              checked={unusedOnly}
              onChange={(e) => setUnusedOnly(e.target.checked)}
              className="sr-only"
            />
            <div
              className={`w-8 h-4 rounded-full transition-colors ${
                unusedOnly ? 'bg-brand-gold' : 'bg-gray-300'
              }`}
            />
            <div
              className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                unusedOnly ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </div>
        </label>
      </div>

      {/* Image grid */}
      {isLoading ? (
        <div className="text-center py-8 text-gray-400 text-sm">Loading images...</div>
      ) : images.length === 0 ? (
        <div className="text-center py-8 text-gray-400 text-sm">
          No images found for this theme
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-2 max-h-64 overflow-y-auto pr-1">
          {images.map((image) => (
            <button
              key={image.id}
              onClick={() => handleSelect(image)}
              className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all hover:opacity-90 ${
                selectedId === image.id
                  ? 'border-brand-gold shadow-md'
                  : 'border-transparent'
              }`}
            >
              <img
                src={getImageUrl(image)}
                alt={image.prompt_or_query || 'Library image'}
                className="w-full h-full object-cover"
                loading="lazy"
              />
              {image.used_by && image.used_by.length > 0 && (
                <span className="absolute top-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded-full">
                  {image.used_by.length}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* AI Generate section */}
      <div className="border-t border-gray-100 pt-3">
        <label className="text-xs font-body text-gray-500 mb-1 block">AI Generate</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            placeholder="Describe the image you want..."
            className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-300"
          />
          <button
            disabled={!aiPrompt.trim() || aiGenerating}
            onClick={async () => {
              setAiGenerating(true);
              try {
                const result = await generateAiImage(null, aiPrompt);
                setAiPrompt('');
                queryClient.invalidateQueries({ queryKey: ['image-library'] });
              } catch {
                // AI generation may not work without a content ID
              } finally {
                setAiGenerating(false);
              }
            }}
            className="flex items-center gap-1 px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {aiGenerating ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>
    </div>
  );
}
