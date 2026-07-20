import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Mic, RotateCw, Smartphone, X, XCircle } from "lucide-react";
import clsx from "clsx";

import { useAudioLevel } from "@/hooks/useAudioLevel";
import { activeMicLabel, isIPhoneMic, type useMicrophoneDevices } from "@/hooks/useMicrophoneDevices";
import type { useVoiceOrb } from "@/hooks/useVoiceOrb";

type Voice = ReturnType<typeof useVoiceOrb>;
type Mic = ReturnType<typeof useMicrophoneDevices>;

function Row({ label, ok, value }: { label: string; ok: boolean | null; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-xs text-jarvis-muted">{label}</span>
      <span className="flex items-center gap-1.5 text-xs font-medium text-jarvis-text">
        {ok === true && <CheckCircle2 className="h-3.5 w-3.5 text-jarvis-emerald" />}
        {ok === false && <XCircle className="h-3.5 w-3.5 text-jarvis-rose" />}
        {value}
      </span>
    </div>
  );
}

/**
 * Microphone diagnostics — the "prove it works before trusting it" panel the
 * spec asks for. Runs its OWN short-lived audio-level probe (independent of
 * the orb's engine) so you can watch a live input meter and confirm the OS
 * is actually delivering audio, list detected input devices, see the selected
 * input + permission status, and check whether browser speech recognition is
 * even available in this context. No secrets — purely local device state.
 */
export default function MicDiagnosticPanel({
  open,
  onClose,
  voice,
  mic,
}: {
  open: boolean;
  onClose: () => void;
  voice: Voice;
  mic: Mic;
}) {
  const {
    supported: devicesSupported,
    devices,
    selectedId,
    permissionGranted,
    requestAccess,
    selectDevice,
    refresh,
  } = mic;
  const probe = useAudioLevel();
  const [probing, setProbing] = useState(false);

  // Start/stop the live probe with the panel's open state.
  useEffect(() => {
    if (!open) {
      probe.stop();
      setProbing(false);
      return;
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => () => probe.stop(), [probe]);

  async function toggleProbe() {
    if (probing) {
      probe.stop();
      setProbing(false);
    } else {
      const ok = await probe.start(selectedId || undefined);
      setProbing(ok);
      if (ok) refresh();
    }
  }

  // Switch input without restarting: persist the choice, and if the live
  // meter is running, re-open it on the new device so it reflects the switch
  // immediately (e.g. laptop mic → iPhone Continuity mic).
  async function changeDevice(id: string) {
    if (id) requestAccess(id);
    else selectDevice("");
    if (probing) {
      probe.stop();
      const ok = await probe.start(id || undefined);
      setProbing(ok);
    }
  }

  const activeLabel = activeMicLabel(devices, selectedId);
  const activeIsIPhone = isIPhoneMic(activeLabel);

  const permissionValue = permissionGranted
    ? "Granted"
    : voice.state === "permission-denied"
      ? "Denied"
      : "Not yet requested";

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="hud-panel hud-corner fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 p-5"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mic className="h-4 w-4 text-jarvis-cyan" />
                <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                  MICROPHONE DIAGNOSTICS
                </h2>
              </div>
              <button
                onClick={onClose}
                className="press-scale rounded-lg p-1 text-jarvis-muted transition hover:text-jarvis-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Live input meter */}
            <div className="mb-3 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs uppercase tracking-wide text-jarvis-muted">Live input level</span>
                <button
                  onClick={toggleProbe}
                  className={clsx(
                    "press-scale rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition",
                    probing
                      ? "border-jarvis-rose/50 bg-jarvis-rose/10 text-jarvis-rose"
                      : "border-jarvis-cyan/40 bg-jarvis-cyan/10 text-jarvis-cyan"
                  )}
                >
                  {probing ? "Stop test" : "Test mic"}
                </button>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-jarvis-panel3/60">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-jarvis-cyan to-jarvis-emerald transition-[width] duration-75"
                  style={{ width: `${Math.round((probing ? probe.level : 0) * 100)}%` }}
                />
              </div>
              <p className="mt-1.5 text-[10px] text-jarvis-faint">
                {probing
                  ? "Speak — the bar should move. If it stays flat, the OS isn't sending audio from this input."
                  : "Click “Test mic” and speak to confirm your microphone is capturing."}
              </p>
              {probe.error && (
                <p className="mt-1 text-[11px] text-jarvis-rose">
                  {probe.error === "permission-denied"
                    ? "Permission denied — allow mic access in the browser."
                    : probe.error === "insecure"
                      ? "Needs a secure context (https/localhost)."
                      : probe.error === "no-device"
                        ? "No microphone found."
                        : "Couldn't open the microphone."}
                </p>
              )}
            </div>

            {/* Status rows */}
            <div className="divide-y divide-jarvis-border/40">
              <Row label="Secure context (https/localhost)" ok={voice.secureContext} value={voice.secureContext ? "Yes" : "No"} />
              <Row label="Microphone API" ok={voice.micSupported} value={voice.micSupported ? "Available" : "Unavailable"} />
              <Row
                label="Speech recognition"
                ok={voice.recognitionSupported}
                value={voice.recognitionSupported ? "Available" : "Not in this browser"}
              />
              <Row
                label="Permission"
                ok={permissionGranted ? true : voice.state === "permission-denied" ? false : null}
                value={permissionValue}
              />
              <Row label="Detected inputs" ok={devices.length > 0 ? true : null} value={String(devices.length)} />
            </div>

            {/* Active microphone — shown clearly, badged when it's an iPhone. */}
            <div className="mt-3 flex items-center justify-between gap-2 rounded-xl border border-jarvis-cyan/30 bg-jarvis-cyan/[0.06] px-3 py-2">
              <span className="text-xs uppercase tracking-wide text-jarvis-muted">Active input</span>
              <span className="flex min-w-0 items-center gap-1.5 text-xs font-medium text-jarvis-text">
                {activeIsIPhone ? (
                  <Smartphone className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan" />
                ) : (
                  <Mic className="h-3.5 w-3.5 shrink-0 text-jarvis-cyan" />
                )}
                <span className="truncate">{activeLabel}</span>
                {activeIsIPhone && (
                  <span className="shrink-0 rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-jarvis-cyan">
                    iPhone
                  </span>
                )}
              </span>
            </div>

            {/* Device selector + manual refresh */}
            {devicesSupported && (
              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-xs uppercase tracking-wide text-jarvis-muted">Selected input</label>
                  <button
                    onClick={() => {
                      // Priming permission first makes freshly-plugged devices
                      // (like an iPhone that just connected) show real labels.
                      if (!permissionGranted) requestAccess();
                      refresh();
                    }}
                    className="press-scale flex items-center gap-1 rounded-lg border border-jarvis-border bg-jarvis-panel2/60 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
                    title="Re-scan for input devices (e.g. an iPhone that just connected)"
                  >
                    <RotateCw className="h-3 w-3" />
                    Refresh devices
                  </button>
                </div>
                <select
                  value={selectedId}
                  onFocus={() => {
                    if (!permissionGranted) requestAccess();
                  }}
                  onChange={(e) => changeDevice(e.target.value)}
                  className="w-full rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text focus:border-jarvis-cyan/50 focus:outline-none"
                >
                  <option value="">System default microphone</option>
                  {devices.map((d, i) => (
                    <option key={d.deviceId || i} value={d.deviceId}>
                      {isIPhoneMic(d.label) ? "📱 " : ""}
                      {d.label || `Microphone ${i + 1}`}
                    </option>
                  ))}
                </select>
                <p className="mt-1.5 text-[10px] text-jarvis-faint">
                  Note: browser speech recognition follows your OS/site default input regardless of this choice — set
                  the same device as default in macOS Sound settings if it isn't picked up. The live meter above does
                  follow this selection.
                </p>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
