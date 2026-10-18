// The four lucide strokes the Paper design uses. Inline so there is no icon dependency.
const base = { width: 14, height: 14, viewBox: "0 0 24 24", fill: "none", strokeWidth: 2.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const Sparkle = ({ className = "" }: { className?: string }) => (
  <svg {...base} width={12} height={12} stroke="currentColor" className={className}>
    <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z" />
  </svg>
);
export const Bolt = () => (
  <svg {...base} width={13} height={13} stroke="currentColor">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);
export const Wand = () => (
  <svg {...base} width={18} height={18} strokeWidth={2} stroke="#6366F1">
    <path d="M15 4V2M15 16v-2M8 9h2M20 9h2M17.8 11.8 19 13M15 9h0M17.8 6.2 19 5m-16 16 9-9M12.2 6.2 11 5" />
  </svg>
);
export const Chevron = ({ down = false }: { down?: boolean }) => (
  <svg {...base} width={10} height={10} stroke="currentColor">
    {down ? <polyline points="6 9 12 15 18 9" /> : <polyline points="9 18 15 12 9 6" />}
  </svg>
);
