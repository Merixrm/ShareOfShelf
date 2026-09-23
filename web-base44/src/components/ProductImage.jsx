import React from 'react';

// Stylized product "bottle" rendered as SVG so every product has a consistent,
// premium-looking visual without relying on external images.
export default function ProductImage({ product, brandColor, flavorColor, label, size = 56, className = '' }) {
  const body = brandColor || product?.color || '#334155';
  const cap = flavorColor || product?.flavorColor || '#94a3b8';
  const name = label || product?.brand || '';
  const flavor = product?.flavor || '';

  return (
    <div
      className={`relative inline-flex items-center justify-center overflow-hidden rounded-lg bg-muted ${className}`}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id={`g-${body}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={body} stopOpacity="0.85" />
            <stop offset="100%" stopColor={body} stopOpacity="1" />
          </linearGradient>
        </defs>
        {/* cap */}
        <rect x="40" y="8" width="20" height="9" rx="2" fill={cap} opacity="0.95" />
        {/* neck */}
        <rect x="42" y="16" width="16" height="8" fill={body} opacity="0.85" />
        {/* body */}
        <path d="M34 26 Q34 22 38 22 L62 22 Q66 22 66 26 L66 86 Q66 92 60 92 L40 92 Q34 92 34 86 Z" fill={`url(#g-${body})`} />
        {/* highlight */}
        <rect x="38" y="30" width="5" height="54" rx="2.5" fill="#ffffff" opacity="0.18" />
        {/* label band */}
        <rect x="34" y="46" width="32" height="22" fill="#ffffff" opacity="0.92" />
        <rect x="34" y="46" width="32" height="4" fill={cap} opacity="0.9" />
        <rect x="34" y="64" width="32" height="4" fill={cap} opacity="0.9" />
      </svg>
      {flavor && (
        <span className="absolute inset-x-0 top-1/2 mt-1 -translate-y-1/2 px-1 text-center text-[8px] font-semibold leading-tight text-foreground/80 line-clamp-2">
          {flavor}
        </span>
      )}
      {name && (
        <span className="absolute bottom-1 left-1 right-1 truncate rounded bg-foreground/70 px-1 text-center text-[7px] font-bold text-white">
          {name}
        </span>
      )}
    </div>
  );
}