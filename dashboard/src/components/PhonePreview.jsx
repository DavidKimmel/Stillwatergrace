const FONT_CSS_MAP = {
  georgia: 'Georgia, serif',
  playfair: '"Playfair Display", Georgia, serif',
  lato: 'Lato, sans-serif',
  calibri: 'Calibri, sans-serif',
};

export default function PhonePreview({ text, imageUrl, contentType, fontSize = 18, fontFamily = 'georgia', textColor = '#FFFFFF' }) {
  const formatLabel = (type) =>
    (type || 'post')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());

  const resolvedFont = FONT_CSS_MAP[fontFamily] || FONT_CSS_MAP.georgia;

  return (
    <div className="flex justify-center">
      {/* iPhone frame */}
      <div className="relative w-[280px] h-[560px] bg-black rounded-[40px] p-[10px] shadow-2xl">
        {/* Notch */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[120px] h-[28px] bg-black rounded-b-2xl z-20" />

        {/* Screen */}
        <div className="relative w-full h-full rounded-[30px] overflow-hidden bg-gradient-to-b from-brand-green/80 to-brand-green/40">
          {/* Background image */}
          {imageUrl ? (
            <img
              src={imageUrl}
              alt="Preview"
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-brand-green via-brand-green-light to-brand-gold/30" />
          )}

          {/* Dark overlay for text readability */}
          <div className="absolute inset-0 bg-black/30" />

          {/* Content overlay */}
          <div className="relative z-10 flex flex-col h-full">
            {/* Status bar area */}
            <div className="h-10" />

            {/* Content type badge */}
            <div className="px-4 pt-2">
              <span className="inline-block bg-brand-gold/90 text-white text-[10px] font-body uppercase tracking-wider px-2 py-0.5 rounded-full">
                {formatLabel(contentType)}
              </span>
            </div>

            {/* Text area */}
            <div className="flex-1 flex items-center px-5">
              {text ? (
                <p
                  className="leading-relaxed drop-shadow-lg"
                  style={{ fontSize: `${fontSize}px`, fontFamily: resolvedFont, color: textColor }}
                >
                  {text}
                </p>
              ) : (
                <p className="text-white/50 font-body text-sm italic">
                  Your text will appear here...
                </p>
              )}
            </div>

            {/* Watermark */}
            <div className="px-4 pb-3">
              <span className="text-white/60 text-[10px] font-body">
                @stillwatergrace
              </span>
            </div>

            {/* Home bar */}
            <div className="flex justify-center pb-2">
              <div className="w-[100px] h-[4px] bg-white/40 rounded-full" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
