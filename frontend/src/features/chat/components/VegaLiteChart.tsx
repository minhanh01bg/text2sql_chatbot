"use client";

import { useEffect, useRef } from "react";
import type { VegaLiteSpec } from "../utils/vegaLiteFormatter";

type VegaLiteChartProps = {
  spec: VegaLiteSpec | null;
  className?: string;
};

/**
 * Render Vega-Lite spec bằng vega-embed (client-only).
 * Spec được format từ sqlTableToVegaLiteSpec.
 */
export function VegaLiteChart({ spec, className }: VegaLiteChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!spec || !containerRef.current) return;

    let cancelled = false;
    const node = containerRef.current;
    node.innerHTML = "";

    import("vega-embed").then(({ default: vegaEmbed }) => {
      if (cancelled || !node) return;
      vegaEmbed(node, spec, {
        actions: false,
        renderer: "canvas",
      }).catch((err: Error) => {
        if (!cancelled && node) {
          node.innerHTML = `<p class="text-sm text-rose-600">Lỗi render Vega-Lite: ${err.message}</p>`;
        }
      });
    });

    return () => {
      cancelled = true;
      node.innerHTML = "";
    };
  }, [spec]);

  if (!spec) return null;

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ minHeight: (spec.height as number) || 320 }}
    />
  );
}
