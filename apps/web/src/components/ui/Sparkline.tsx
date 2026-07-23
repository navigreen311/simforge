// Pure inline-SVG sparkline (server-renderable, no client JS).

export function Sparkline({
  points,
  width = 160,
  height = 36,
}: {
  points: number[];
  width?: number;
  height?: number;
}) {
  if (points.length === 0) return null;
  const max = Math.max(1, ...points);
  const step = points.length > 1 ? width / (points.length - 1) : width;
  const path = points
    .map((v, i) => {
      const x = i * step;
      const y = height - (v / max) * (height - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const last = points[points.length - 1];
  const lastY = height - (last / max) * (height - 4) - 2;

  return (
    <svg width={width} height={height} className="overflow-visible">
      <path d={path} fill="none" stroke="#D4AF37" strokeWidth="1.5" />
      <circle cx={(points.length - 1) * step} cy={lastY} r="2.5" fill="#D4AF37" />
    </svg>
  );
}
