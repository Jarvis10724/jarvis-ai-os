import { useCallback, useEffect, useState } from "react";

const MIC_DEVICE_KEY = "jarvis_mic_device_id";

function readStoredDeviceId(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(MIC_DEVICE_KEY) || "";
  } catch {
    return "";
  }
}

/**
 * True for an Apple Continuity Camera iPhone microphone — macOS labels these
 * "<name>'s iPhone Microphone" / "iPhone Microphone". Used only to badge the
 * device in the picker/diagnostics; no automatic selection or fallback.
 */
export function isIPhoneMic(label?: string | null): boolean {
  return !!label && /iphone/i.test(label);
}

/** Human label for whichever input is currently selected ("" = OS default). */
export function activeMicLabel(devices: MediaDeviceInfo[], selectedId: string): string {
  if (!selectedId) return "System default microphone";
  const d = devices.find((x) => x.deviceId === selectedId);
  return d?.label || "Selected microphone";
}

interface UseMicrophoneDevicesReturn {
  /** Whether this browser exposes device enumeration at all. */
  supported: boolean;
  /** Audio input devices — labels are blank until permission is granted. */
  devices: MediaDeviceInfo[];
  /** Persisted preferred device id ("" = system default). */
  selectedId: string;
  /** True once we've been granted mic access at least once (so labels show). */
  permissionGranted: boolean;
  /** Re-reads the device list (e.g. after a USB mic is plugged in). */
  refresh: () => Promise<void>;
  /**
   * Requests mic permission (optionally pinned to one device) just long
   * enough to populate real device labels and "warm up" that device as the
   * one the browser/OS treats as active for this site, then immediately
   * releases the stream — recognition itself opens its own stream later.
   */
  requestAccess: (deviceId?: string) => Promise<void>;
  selectDevice: (deviceId: string) => void;
}

/**
 * Lets the user pick a preferred microphone (e.g. a USB mic sitting
 * alongside a laptop's built-in one) and keeps that choice for future
 * sessions. Important caveat, surfaced in the UI rather than hidden: the
 * Web Speech API (what useSpeechRecognition is built on) has no way to pin
 * recognition itself to a specific input device — it always follows
 * whatever the browser/OS currently treats as the default microphone for
 * this site. Granting/selecting a device here does help browsers that key
 * off "last device this site used," but the only universally reliable fix
 * is setting the USB mic as the OS (or per-site Chrome) default input.
 */
export function useMicrophoneDevices(): UseMicrophoneDevicesReturn {
  const supported =
    typeof navigator !== "undefined" && !!navigator.mediaDevices?.enumerateDevices;

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedId, setSelectedIdState] = useState<string>(readStoredDeviceId);
  const [permissionGranted, setPermissionGranted] = useState(false);

  const refresh = useCallback(async () => {
    if (!supported) return;
    try {
      const list = await navigator.mediaDevices.enumerateDevices();
      const inputs = list.filter((d) => d.kind === "audioinput");
      setDevices(inputs);
      if (inputs.some((d) => d.label)) setPermissionGranted(true);
    } catch {
      // enumerateDevices can throw in locked-down contexts — leave list empty.
    }
  }, [supported]);

  useEffect(() => {
    refresh();
    if (!supported) return;
    // Picks up a USB mic being plugged/unplugged without a manual refresh.
    navigator.mediaDevices.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices.removeEventListener("devicechange", refresh);
  }, [refresh, supported]);

  function selectDevice(deviceId: string) {
    setSelectedIdState(deviceId);
    try {
      window.localStorage.setItem(MIC_DEVICE_KEY, deviceId);
    } catch {
      // ignore storage failures — selection still works for this session
    }
  }

  const requestAccess = useCallback(
    async (deviceId?: string) => {
      if (!supported) return;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: deviceId ? { deviceId: { exact: deviceId } } : true,
        });
        stream.getTracks().forEach((t) => t.stop());
        setPermissionGranted(true);
        await refresh();
        if (deviceId) selectDevice(deviceId);
      } catch {
        // Permission denied or device unplugged — the existing mic-error UI
        // (from useSpeechRecognition) surfaces this on the next listen attempt.
      }
    },
    [supported, refresh]
  );

  return { supported, devices, selectedId, permissionGranted, refresh, requestAccess, selectDevice };
}
