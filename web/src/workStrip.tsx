// The one status strip (ticket 0083, spec §11): what Kiripix is working on, for how long, and how many actions wait. It is
// drawn from what the screen itself knows (an action started, an action ended), so it shows at once and needs no event; the
// latest progress message and a fraction are added only when the event stream gives them.

import { useEffect, useState } from "react";

export interface Working {
  label: string;
  since: number; // when it began (Date.now())
  waiting: number; // actions behind it, still queued
  progress: string | null;
  fraction: number | null; // only where an event gave a real one
}

export function elapsedText(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}

export function WorkStrip({ working }: { working: Working | null }) {
  const [now, setNow] = useState(Date.now());
  const active = working !== null;
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [active]);
  return (
    <div className="work-slot" data-testid="work-slot">
      {working && (
        <div className="work-strip" role="status" aria-live="polite" data-testid="work-strip">
          <span className="work-anim" data-testid="work-anim" aria-hidden="true" />
          <span className="work-label" data-testid="work-label">
            {working.label}
          </span>
          <span className="work-elapsed" data-testid="work-elapsed">
            {elapsedText(now - working.since)}
          </span>
          {working.fraction !== null && (
            <progress className="work-bar" data-testid="work-bar" max={1} value={working.fraction} />
          )}
          {working.progress && (
            <span className="work-progress" data-testid="work-progress">
              {working.progress}
            </span>
          )}
          {working.waiting > 0 && (
            <span className="work-waiting" data-testid="work-waiting">
              {working.waiting} waiting
            </span>
          )}
        </div>
      )}
    </div>
  );
}
