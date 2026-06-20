"use client";

import * as React from "react";
import { SwitchCamera, CameraOff, Loader2 } from "lucide-react";

type Facing = "environment" | "user";

// Fraction of the shorter screen/video dimension used as the scan square.
// 0.65 = the square covers 65% of the shorter side, centered.
const SCAN_FRACTION = 0.65;

interface CameraViewProps {
  /** Called with a square JPEG data URL when the user taps capture. */
  onCapture: (dataUrl: string) => void;
  busy?: boolean;
  /** Optional ref populated with { capture } so the Arduino trigger can fire it. */
  triggerRef?: React.MutableRefObject<{ capture: () => void } | null>;
  /** When true, fires capture as soon as the camera stream is ready. */
  autoCapture?: boolean;
  /** Called immediately after autoCapture fires so the parent can clear the flag. */
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

  // Expose capture() to the parent so the Arduino trigger can fire it remotely.
  React.useEffect(() => {
    if (triggerRef) triggerRef.current = { capture };
    return () => { if (triggerRef) triggerRef.current = null; };
  });

  // If we were navigated back from the result screen with autoCapture set,
  // fire as soon as the video stream is ready.
  React.useEffect(() => {
    if (autoCapture && ready) {
      onAutoCaptureConsumed?.();
      capture();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoCapture, ready]);

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
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
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
    return () => {
      cancelled = true;
      stop();
    };
  }, [facing, stop]);

  function capture() {
    const video = videoRef.current;
    if (!video || !ready) return;
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return;

    // Crop to the scan square (SCAN_FRACTION of the shorter dimension, centered).
    const outerSide = Math.min(w, h);
    const side = Math.round(outerSide * SCAN_FRACTION);
    const sx = (w - side) / 2;
    const sy = (h - side) / 2;

    const canvas = document.createElement("canvas");
    canvas.width = side;
    canvas.height = side;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, sx, sy, side, side, 0, 0, side, side);
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

      {/* scan square — visual guide; capture crops to this exact region */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div
          className="border-2 border-white"
          style={{ width: `${SCAN_FRACTION * 100}vmin`, height: `${SCAN_FRACTION * 100}vmin` }}
        />
      </div>

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
