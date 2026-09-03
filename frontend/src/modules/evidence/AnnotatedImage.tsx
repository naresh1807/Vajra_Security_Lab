import type { CSSProperties } from "react";
import type { EvidenceAnnotation } from "../../types";

/**
 * A screenshot with its non-destructive markup drawn on top. Shapes are in
 * image-relative coordinates (0..1), so this stays correct at any rendered
 * size. Redaction boxes are fully opaque - they hide content in the app.
 */
export function AnnotatedImage({
  src,
  alt,
  annotations,
  className,
}: {
  src: string;
  alt: string;
  annotations: EvidenceAnnotation[];
  className?: string;
}) {
  return (
    <div className={`relative overflow-hidden ${className ?? ""}`}>
      <img src={src} alt={alt} className="block w-full" />
      <div className="pointer-events-none absolute inset-0">
        {annotations.map((shape, i) => (
          <Shape key={i} shape={shape} />
        ))}
      </div>
    </div>
  );
}

function pct(v: number): string {
  return `${v * 100}%`;
}

function Shape({ shape }: { shape: EvidenceAnnotation }) {
  if (shape.type === "arrow") {
    return (
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <line
          x1={shape.x * 100}
          y1={shape.y * 100}
          x2={(shape.x2 ?? shape.x) * 100}
          y2={(shape.y2 ?? shape.y) * 100}
          stroke={shape.color}
          strokeWidth={0.8}
          markerEnd="url(#vajra-arrowhead)"
        />
        <defs>
          <marker id="vajra-arrowhead" markerWidth="6" markerHeight="6" refX="4" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill={shape.color} />
          </marker>
        </defs>
      </svg>
    );
  }

  const box: CSSProperties = {
    left: pct(shape.x),
    top: pct(shape.y),
    width: pct(shape.w ?? 0),
    height: pct(shape.h ?? 0),
  };

  if (shape.type === "redact") {
    return <div className="absolute bg-black" style={box} />;
  }
  if (shape.type === "label") {
    return (
      <div
        className="absolute flex items-center justify-center px-1 text-center text-[11px] font-semibold leading-tight text-white"
        style={{ ...box, background: shape.color }}
      >
        {shape.text}
      </div>
    );
  }
  // highlight
  return (
    <div className="absolute rounded-sm" style={{ ...box, border: `2px solid ${shape.color}` }} />
  );
}
