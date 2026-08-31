"use client";

import { useEffect, useRef, useState } from "react";

import type { GlobeMarker } from "./globe-model";

const MANILA_LONGITUDE = 120.9842;
const INITIAL_PHI = (MANILA_LONGITUDE * Math.PI) / 180;
const INITIAL_THETA = 0.12;
const AUTO_ROTATE_SPEED = 0.0018;

type TrafficGlobeProps = {
  markers: GlobeMarker[];
  locationCount: number;
};

type GlobeHandle = { update: (state: object) => void; destroy: () => void };

/**
 * A small client-only adapter around Cobe's imperative WebGL canvas.
 *
 * The ranked list remains the source of exact values. This globe supplies
 * spatial context and intentionally has no labels that could compete with or
 * obscure those figures.
 */
export function TrafficGlobe({ markers, locationCount }: TrafficGlobeProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const markersRef = useRef(markers);
  const phiRef = useRef(INITIAL_PHI);
  const draggingRef = useRef(false);
  const pointerXRef = useRef(0);
  const globeRef = useRef<GlobeHandle | null>(null);
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    markersRef.current = markers;
    globeRef.current?.update({ markers });
  }, [markers]);

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    if (!host || !canvas) return;
    const canvasElement = canvas;

    let disposed = false;
    let frame = 0;
    let size = Math.max(240, Math.floor(host.clientWidth));
    let globe: GlobeHandle | null = null;
    let scheduleAnimation = () => {};
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    const resize = () => {
      const nextSize = Math.max(240, Math.floor(host.clientWidth));
      if (nextSize === size) return;
      size = nextSize;
      globe?.update({ width: size, height: size });
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);

    const onContextLost = (event: Event) => {
      event.preventDefault();
      cancelAnimationFrame(frame);
      setUnavailable(true);
    };
    canvasElement.addEventListener("webglcontextlost", onContextLost);
    const onMotionChange = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      scheduleAnimation();
    };
    reduceMotion.addEventListener("change", onMotionChange);

    async function start() {
      try {
        // Cobe is browser-only and not needed until this authenticated panel
        // mounts, so keep it out of the server-rendering path.
        const { default: createGlobe } = await import("cobe");
        if (disposed) return;

        globe = createGlobe(canvasElement, {
          width: size,
          height: size,
          devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
          phi: phiRef.current,
          theta: INITIAL_THETA,
          dark: 0,
          diffuse: 1.1,
          scale: 0.94,
          mapSamples: 16_000,
          // Light treatment: a near-white sphere, medium-grey land dots, and a
          // light-neutral glow that stays close to the --surface-app backdrop so
          // the halo never reads as a smudge. Cobe darkens land against the base
          // when `dark` is 0, so mapBrightness sets how grey the land reads.
          mapBrightness: 0.72,
          mapBaseBrightness: 0.04,
          baseColor: [0.96, 0.96, 0.965],
          markerColor: [0.937, 0.345, 0.129],
          glowColor: [0.82, 0.82, 0.84],
          markerElevation: 0.025,
          markers: markersRef.current,
        });
        globeRef.current = globe;
        const context =
          canvasElement.getContext("webgl2") ?? canvasElement.getContext("webgl");
        if (!context) {
          globe.destroy();
          globe = null;
          globeRef.current = null;
          setUnavailable(true);
          return;
        }
        if (disposed) {
          globe.destroy();
          globe = null;
          return;
        }

        setReady(true);
        const draw = () => {
          frame = 0;
          if (!globe || disposed) return;
          if (reduceMotion.matches) return;
          if (!draggingRef.current) phiRef.current += AUTO_ROTATE_SPEED;
          globe.update({
            phi: phiRef.current,
            theta: INITIAL_THETA,
          });
          frame = requestAnimationFrame(draw);
        };
        scheduleAnimation = () => {
          if (!disposed && !reduceMotion.matches && frame === 0) {
            frame = requestAnimationFrame(draw);
          }
        };
        scheduleAnimation();
      } catch {
        if (!disposed) setUnavailable(true);
      }
    }

    void start();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      canvasElement.removeEventListener("webglcontextlost", onContextLost);
      reduceMotion.removeEventListener("change", onMotionChange);
      globe?.destroy();
      globeRef.current = null;

      // Cobe wraps the canvas so it can host marker anchors. Restore the DOM
      // before React's Strict Mode re-runs this effect, otherwise wrappers nest.
      const generatedWrapper = canvasElement.parentElement;
      if (generatedWrapper && generatedWrapper !== host) {
        host.appendChild(canvasElement);
        generatedWrapper.remove();
      }
    };
  }, []);

  const label = locationCount
    ? `Interactive globe showing request activity across ${locationCount} location${locationCount === 1 ? "" : "s"}. Drag or use the left and right arrow keys to rotate. Exact values are listed beside the globe.`
    : "Interactive request-location globe with no markers. Exact values are listed beside the globe.";

  return (
    <div className="relative aspect-square w-full">
      {/* Keep Cobe's DOM-mutating wrapper isolated from React-owned overlays.
          React always sees one stable canvas inside this host. */}
      <div ref={hostRef} className="absolute inset-0">
        <canvas
          ref={canvasRef}
          role="img"
          aria-label={label}
          aria-hidden={unavailable}
          className={`h-full w-full touch-pan-y select-none transition-opacity duration-300 ${
            ready && !unavailable
              ? "cursor-grab opacity-100 active:cursor-grabbing"
              : "opacity-0"
          }`}
          onPointerDown={(event) => {
            draggingRef.current = true;
            pointerXRef.current = event.clientX;
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!draggingRef.current) return;
            const delta = event.clientX - pointerXRef.current;
            pointerXRef.current = event.clientX;
            phiRef.current += delta / 180;
            globeRef.current?.update({ phi: phiRef.current, theta: INITIAL_THETA });
          }}
          onPointerUp={(event) => {
            draggingRef.current = false;
            if (event.currentTarget.hasPointerCapture(event.pointerId)) {
              event.currentTarget.releasePointerCapture(event.pointerId);
            }
          }}
          onPointerCancel={() => {
            draggingRef.current = false;
          }}
          tabIndex={unavailable ? -1 : 0}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault();
              phiRef.current += event.key === "ArrowLeft" ? -0.12 : 0.12;
              globeRef.current?.update({ phi: phiRef.current, theta: INITIAL_THETA });
            }
          }}
        />
      </div>

      {!ready && !unavailable ? (
        <div className="pointer-events-none absolute inset-0 animate-pulse rounded-full bg-[var(--surface-card)] motion-reduce:animate-none" />
      ) : null}

      {ready && !unavailable ? (
        <p
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-1 text-center text-[11px] text-[var(--text-muted)]"
        >
          Drag to rotate
        </p>
      ) : null}

      {unavailable ? (
        <div
          className="absolute inset-0 flex items-center justify-center rounded-full border border-[var(--border-subtle)] bg-[var(--surface-card)] p-8 text-center"
          role="status"
        >
          <p className="max-w-56 text-[13px] leading-relaxed text-[var(--text-secondary)]">
            The interactive globe is unavailable in this browser. The ranked location
            list still contains every displayed value.
          </p>
        </div>
      ) : null}
    </div>
  );
}
