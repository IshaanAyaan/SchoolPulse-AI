"use client";

import * as React from "react";
import { SwitchCamera, CameraOff, Loader2 } from "lucide-react";

import { meanAbsDiff } from "@/lib/background-diff.mjs";

type Facing = "environment" | "user";

// Resolution at which we store the baseline and apply the pixel-level mask.
// 2× the model's 224 input — good quality while keeping arrays manageable.
const MASK_SIZE = 448;

// Per-pixel grayscale difference below which a pixel is considered "background"
// (part of the empty tray) and gets replaced with white.
const PIXEL_DIFF_THRESHOLD = 25; // out of 255

// 48×48 downsample used only for the fast baseline-refresh guard.
const GRID = 48;
const REFRESH_MAX_DIFF = 0.04;

// Module-level so baselines survive the camera unmount/remount each scan cycle.
let baselineGray: Uint8ClampedArray | null = null;   // 48×48 for refresh guard
let baselineMask: Uint8ClampedArray | null = null;   // MASK_SIZE×MASK_SIZE grayscale

interface CameraViewProps {
  onCapture: (dataUrl: string) => void;
  busy?: boolean;
  triggerRef?: React.MutableRefObject<{ capture: () => void } | null>;
  autoCapture?: boolean;
  onAutoCaptureConsumed?: () => void;
}

export function CameraView({
  onCapture,
  busy = false,
  triggerRef,
  autoCapture = false,
  onAutoCaptureConsumed,
}: CameraViewProps) {
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const streamRef = React.useRef<MediaStream | null>(null);
  const [facing, setFacing] = React.useState<Facing>("environment");
  const [error, setError] = React.useState<string | null>(null);
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    if (triggerRef) triggerRef.current = { capture };
    return () => { if (triggerRef) triggerRef.current = null; };
  });

  React.useEffect(() => {
    if (autoCapture && ready) {
      onAutoCaptureConsumed?.();
      capture();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoCapture, ready]);

  // Sample the full frame at a given size and return grayscale pixels.
  const sampleGrayscale = React.useCallback((size: number): Uint8ClampedArray | null => {
    const video = videoRef.current;
    if (!video || !ready) return null;
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return null;

    const c = document.createElement("canvas");
    c.width = size;
    c.height = size;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    if (!ctx) return null;
    // Center square crop of the full frame, downsampled to `size`.
    const side = Math.min(w, h);
    const sx = (w - side) / 2;
    const sy = (h - side) / 2;
    ctx.drawImage(video, sx, sy, side, side, 0, 0, size, size);
    const { data } = ctx.getImageData(0, 0, size, size);
    const gray = new Uint8ClampedArray(size * size);
    for (let i = 0, p = 0; i < data.length; i += 4, p++) {
      gray[p] = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) | 0;
    }
    return gray;
  }, [ready]);

  // Maintain the empty-tray baseline. Update only when the scene is stable
  // (no object present) so we never accidentally bake the item into the baseline.
  React.useEffect(() => {
    if (!ready) return;
    const maintain = () => {
      if (busy || autoCapture) return;
      const g = sampleGrayscale(GRID);
      if (!g) return;
      if (!baselineGray || meanAbsDiff(g, baselineGray) < REFRESH_MAX_DIFF) {
        baselineGray = g;
        // Also update the high-res mask baseline when the scene is stable.
        const m = sampleGrayscale(MASK_SIZE);
        if (m) baselineMask = m;
      }
    };
    maintain();
    const id = setInterval(maintain, 1500);
    return () => clearInterval(id);
  }, [ready, busy, autoCapture, sampleGrayscale]);

  const stop = React.useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    setReady(false);
    setError(null);

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Camera API unavailable. Use HTTPS (or localhost) in Safari/Chrome.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 1280 } },
          audio: false,
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
        setReady(true);
      } catch (err) {
        const name = err instanceof DOMException ? err.name : "";
        setError(
          name === "NotAllowedError"
            ? "Camera permission denied. Allow camera access and reload."
            : "Could not open the camera. Check it isn't in use by another app."
        );
      }
    }

    start();
    return () => { cancelled = true; stop(); };
  }, [facing, stop]);

  function capture() {
    const video = videoRef.current;
    if (!video || !ready) return;
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return;

    // Always capture when the ultrasonic sensor triggers.
    // Draw the center-square crop to a MASK_SIZE canvas.
    const side = Math.min(w, h);
    const sx = (w - side) / 2;
    const sy = (h - side) / 2;

    const canvas = document.createElement("canvas");
    canvas.width = MASK_SIZE;
    canvas.height = MASK_SIZE;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, sx, sy, side, side, 0, 0, MASK_SIZE, MASK_SIZE);

    // Apply background subtraction: pixels that closely match the empty-tray
    // baseline become white so the model only sees the item.
    if (baselineMask) {
      const imageData = ctx.getImageData(0, 0, MASK_SIZE, MASK_SIZE);
      const { data } = imageData;
      for (let i = 0, p = 0; i < data.length; i += 4, p++) {
        const gray = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) | 0;
        if (Math.abs(gray - baselineMask[p]) < PIXEL_DIFF_THRESHOLD) {
          data[i] = 255;     // R → white
          data[i + 1] = 255; // G → white
          data[i + 2] = 255; // B → white
        }
      }
      ctx.putImageData(imageData, 0, 0);
    }

    onCapture(canvas.toDataURL("image/jpeg", 0.9));
  }

  return (
    <div className="relative h-[100dvh] w-screen overflow-hidden bg-black">
      <video
        ref={videoRef}
        playsInline
        muted
        autoPlay
        className="absolute inset-0 h-full w-full object-cover"
        style={facing === "user" ? { transform: "scaleX(-1)" } : undefined}
      />

      {/* top bar — flip button only */}
      <div className="absolute right-0 top-0 p-5">
        <button
          aria-label="Flip camera"
          onClick={() => setFacing((f) => (f === "environment" ? "user" : "environment"))}
          className="flex h-11 w-11 items-center justify-center rounded-full bg-black/40 text-white backdrop-blur transition active:scale-95"
        >
          <SwitchCamera className="h-6 w-6" />
        </button>
      </div>

      {/* capture button */}
      <div className="absolute bottom-0 left-0 right-0 flex flex-col items-center pb-10">
        <button
          aria-label="Capture and sort"
          onClick={capture}
          disabled={!ready || busy}
          className="group flex h-20 w-20 items-center justify-center rounded-full border-4 border-white/90 disabled:opacity-50"
        >
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-white transition group-active:scale-90">
            {busy ? <Loader2 className="h-7 w-7 animate-spin text-black" /> : null}
          </span>
        </button>
      </div>

      {error ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/85 p-8 text-center">
          <CameraOff className="h-10 w-10 text-white/80" />
          <p className="max-w-sm text-white/90">{error}</p>
        </div>
      ) : null}
    </div>
  );
}
