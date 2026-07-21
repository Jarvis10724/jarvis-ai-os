import { useEffect } from "react";

/**
 * Pauses every CSS animation while the browser tab is backgrounded by toggling
 * `.motion-paused` on <html> (see index.css). The AI-OS shell layers a lot of
 * ambient/orbital motion; there's no reason to spend cycles on it when the user
 * isn't looking. Browsers already throttle background rAF, but this makes the
 * pause explicit and immediate. Mount once (from the persistent shell).
 */
export function usePauseOffscreenAnimations(): void {
  useEffect(() => {
    const root = document.documentElement;
    const apply = () => root.classList.toggle("motion-paused", document.hidden);
    apply();
    document.addEventListener("visibilitychange", apply);
    return () => {
      document.removeEventListener("visibilitychange", apply);
      root.classList.remove("motion-paused");
    };
  }, []);
}
