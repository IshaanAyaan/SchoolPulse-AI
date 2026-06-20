"use client";

import * as React from "react";
import { Loader2, AlertTriangle } from "lucide-react";

import { CameraView } from "@/components/camera-view";
import { ResultView } from "@/components/result-view";
import { Button } from "@/components/ui/button";
import type { PredictResult } from "@/lib/types";

type Phase = "camera" | "loading" | "result" | "error";

// The result screen auto-returns to the camera after this long if no feedback is
// given; the thank-you toast clears after this long.
const RESULT_TIMEOUT_MS = 30_000;
const TOAST_TIMEOUT_MS = 3_000;

export default function Home() {
  const [phase, setPhase] = React.useState<Phase>("camera");
  const [photo, setPhoto] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<PredictResult | null>(null);
  const [errorMsg, setErrorMsg] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [toast, setToast] = React.useState<string | null>(null);
  const [activityNonce, setActivityNonce] = React.useState(0);

  // Ref so the capture callback inside the interval always sees the latest value
  // without re-registering the interval on every render.
  const cameraRef = React.useRef<{ capture: () => void } | null>(null);

  // When triggered from the result screen we can't capture immediately (the
  // camera isn't mounted yet). This flag tells CameraView to fire as soon as
  // it's ready.
  const [autoCapture, setAutoCapture] = React.useState(false);

  const reset = React.useCallback(() => {
    setResult(null);
    setPhoto(null);
    setErrorMsg("");
    setPhase("camera");
  }, []);

  // Auto-return to the camera if no one gives feedback. Typing in the correction
  // box bumps activityNonce, restarting the countdown so an active user isn't cut
  // off mid-correction.
  React.useEffect(() => {
    if (phase !== "result") return;
    const t = setTimeout(reset, RESULT_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [phase, activityNonce, reset]);

  // Poll /api/trigger every second on both the camera and result screens.
  // - Camera screen: fire capture immediately via the CameraView ref.
  // - Result screen: reset to camera and set autoCapture so CameraView fires
  //   as soon as the video stream is ready.
  React.useEffect(() => {
    if (phase !== "camera" && phase !== "result") return;
    const id = setInterval(async () => {
      try {
        const res = await fetch("/api/trigger");
        const data = await res.json();
        if (!data.triggered) return;
        if (phase === "camera" && cameraRef.current) {
          cameraRef.current.capture();
        } else if (phase === "result") {
          setAutoCapture(true);
          reset();
        }
      } catch {
        // silently ignore — bridge may not be running
      }
    }, 1000);
    return () => clearInterval(id);
  }, [phase, reset]);

  // Auto-dismiss the thank-you toast.
  React.useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), TOAST_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [toast]);

  async function handleCapture(dataUrl: string) {
    setPhoto(dataUrl);
    setPhase("loading");
    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? data?.detail ?? "Prediction failed");
      setResult(data as PredictResult);
      setPhase("result");

      // Tell the Arduino which way to rotate. physical_bin is "Garbage" | "Compost".
      fetch("/api/servo-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: (data.physical_bin as string).toUpperCase() }),
      }).catch(() => {/* best-effort */});
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong");
      setPhase("error");
    }
  }

  async function handleCorrection(correctItem: string) {
    if (!result) return;
    setSubmitting(true);
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prediction_id: result.prediction_id,
          correct_item: correctItem,
        }),
      });
    } catch {
      /* best-effort; never block the kiosk on logging */
    } finally {
      setSubmitting(false);
      setToast("Thank you for your feedback.");
      reset();
    }
  }

  if (phase === "camera") {
    return (
      <>
        <CameraView
          onCapture={handleCapture}
          triggerRef={cameraRef}
          autoCapture={autoCapture}
          onAutoCaptureConsumed={() => setAutoCapture(false)}
        />
        {toast ? (
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center">
            <div className="rounded-xl bg-black/85 px-8 py-5 text-lg font-bold text-white shadow-xl">
              {toast}
            </div>
          </div>
        ) : null}
      </>
    );
  }

  if (phase === "loading") {
    return (
      <main className="relative h-[100dvh] w-screen bg-black">
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photo} alt="Captured item" className="h-full w-full object-cover opacity-40" />
        ) : null}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="text-lg text-white/90">Sorting…</p>
        </div>
      </main>
    );
  }

  if (phase === "error") {
    return (
      <main className="flex h-[100dvh] w-screen flex-col items-center justify-center gap-4 bg-background p-8 text-center">
        <AlertTriangle className="h-12 w-12 text-yellow-500" />
        <p className="max-w-md text-muted-foreground">{errorMsg}</p>
        <Button size="lg" onClick={reset}>
          Try again
        </Button>
      </main>
    );
  }

  // phase === "result"
  return (
    <main>
      {result ? (
        <ResultView
          result={result}
          submitting={submitting}
          onSubmitCorrection={handleCorrection}
          onActivity={() => setActivityNonce((n) => n + 1)}
        />
      ) : null}
    </main>
  );
}
