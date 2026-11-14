// The Owner's active time on a Stage's screen (ticket 0182), logged with `track`. Active means this tab is visible and
// focused and an input event (pointer, key, wheel) came in the last three minutes. A span is sent when the Owner blurs or
// hides the tab, goes idle, or leaves the screen, and every minute while active, so a crash loses at most a minute.
// Nothing is sent while the tab is hidden. Only the Owner's session token lets `track` through. A span refused because a
// run holds the Asset (`lock.busy`) is kept and sent with the next one, so time spent watching a long build still counts;
// any other answer is dropped.

import { useEffect } from "react";
import { call } from "./api";

export const IDLE_MS = 3 * 60 * 1000;
export const FLUSH_SECONDS = 60;
const TICK_MS = 1000;
const MAX_STEP_SECONDS = 5; // a throttled or suspended timer doesn't make a long gap count

export function useActiveTime(asset: string | null, stage: string | null): void {
  useEffect(() => {
    if (!asset || !stage) return;
    let lastInput = Date.now(); // opening the screen is the Owner's doing
    let lastTick = Date.now();
    let pending = 0; // active seconds not yet sent

    const send = (leaving: boolean) => {
      const seconds = Math.round(pending);
      pending = 0;
      if (seconds < 1) return;
      const sent = Math.min(seconds, 3600);
      void call("track", { asset, stage, seconds: sent }, undefined, leaving)
        .then((answer) => {
          if (!answer.ok && answer.findings.some((finding) => finding.code === "lock.busy")) pending += sent;
        })
        .catch(() => undefined);
    };
    const active = (now: number) => !document.hidden && document.hasFocus() && now - lastInput < IDLE_MS;
    const tick = () => {
      const now = Date.now();
      const step = Math.min((now - lastTick) / 1000, MAX_STEP_SECONDS);
      lastTick = now;
      if (active(now)) {
        pending += step;
        if (pending >= FLUSH_SECONDS) send(false);
      } else {
        send(false); // blurred, hidden or idle: the span ends
      }
    };
    const input = () => {
      lastInput = Date.now();
    };
    const away = () => {
      tick();
      send(false);
    };
    const closing = () => send(true);

    const timer = window.setInterval(tick, TICK_MS);
    const inputs = ["pointerdown", "pointermove", "keydown", "wheel"] as const;
    for (const name of inputs) window.addEventListener(name, input, { passive: true });
    window.addEventListener("blur", away);
    document.addEventListener("visibilitychange", away);
    window.addEventListener("pagehide", closing);
    return () => {
      window.clearInterval(timer);
      for (const name of inputs) window.removeEventListener(name, input);
      window.removeEventListener("blur", away);
      document.removeEventListener("visibilitychange", away);
      window.removeEventListener("pagehide", closing);
      tick();
      send(false); // leaving the screen
    };
  }, [asset, stage]);
}
