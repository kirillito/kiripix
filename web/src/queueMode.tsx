// Queue mode (ticket 0329, spec §11): one keyboard flow over every stop that waits on the Owner. The list is `queue`'s, in
// its order; nothing here decides what waits. The keys are handled in App, which owns the Stage's Accept.

import { useState } from "react";
import type { Finding, QueueData, QueueStop } from "./api";

// A stop is the same while its Asset, Stage and kind of stop are, whatever its text or hash does meanwhile.
export function stopKey(stop: QueueStop): string {
  const at = stop.position;
  const where = stop.type === "finding" ? [stop.code, at?.file, at?.x, at?.y, at?.field].join(",") : "";
  return [stop.asset, stop.stage ?? "", stop.type, where].join("|");
}

// A finding's stop as the Finding a click on it would be, so `jump` can take it.
export function stopFinding(stop: QueueStop): Finding {
  return {
    code: stop.code ?? "",
    severity: stop.severity === "error" ? "error" : "warning",
    message: stop.reason ?? "",
    position: stop.position,
    fix: null,
    owner_action: stop.owner_action,
  };
}

const TYPE_LABEL: Record<QueueStop["type"], string> = { review: "Review", input: "Input", finding: "Finding" };

export function QueueButton(props: { count: number | null; active: boolean; onClick: () => void; testid: string }) {
  return (
    <button data-testid={props.testid} aria-pressed={props.active} onClick={props.onClick} title="Walk everything that waits on you">
      Queue{props.count !== null ? ` · ${props.count}` : ""}
    </button>
  );
}

export function QueueStrip(props: {
  queue: QueueData | null;
  findings: Finding[];
  index: number; // -1 when there is no current stop
  match: string;
  onMatch: (match: string) => void;
  onGo: (index: number) => void;
  onLeave: () => void;
}) {
  const { queue } = props;
  const stops = queue?.stops ?? [];
  const stop = stops[props.index];
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    if (draft !== null && draft.trim() !== props.match) props.onMatch(draft.trim());
    setDraft(null);
  };
  const fixes = (queue?.agent_fixable ?? []).flatMap((entry) => entry.fixes.map((fix) => ({ asset: entry.asset, ...fix })));
  const fixable = queue?.counts.agent_fixable ?? 0;
  return (
    <section className="queue-strip" data-testid="queue-strip" aria-label="Queue">
      <div className="queue-row">
        <strong data-testid="queue-position">{stop ? `${props.index + 1} of ${stops.length}` : "Queue empty"}</strong>
        {stop && (
          <span className="queue-type" data-testid="queue-type" data-type={stop.type}>
            {TYPE_LABEL[stop.type]}
          </span>
        )}
        {stop ? (
          <span className="queue-reason" data-testid="queue-reason">
            {stop.stage ? `${stop.asset} ${stop.stage}: ` : `${stop.asset}: `}
            {stop.reason ?? stop.owner_action ?? ""}
          </span>
        ) : (
          <span className="queue-reason">Nothing waits on you{props.match ? ` in ${props.match}` : ""}.</span>
        )}
        <label className="queue-match">
          Match
          <input
            data-testid="queue-match"
            placeholder="room.ch01_*"
            value={draft ?? props.match}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") commit();
              else if (event.key === "Escape") setDraft(null);
            }}
            onBlur={commit}
          />
        </label>
        <button data-testid="queue-prev" disabled={!stop || props.index <= 0} onClick={() => props.onGo(props.index - 1)} title="Previous (← or P)">
          ←
        </button>
        <button
          data-testid="queue-next"
          disabled={!stop || props.index >= stops.length - 1}
          onClick={() => props.onGo(props.index + 1)}
          title="Next (→ or N)"
        >
          →
        </button>
        <button data-testid="queue-leave" onClick={props.onLeave} title="Leave the queue (Esc)">
          Leave
        </button>
      </div>
      {stop && stop.type !== "review" && stop.owner_action && stop.owner_action !== stop.reason && (
        <p className="queue-action" data-testid="queue-owner-action">
          {stop.owner_action}
        </p>
      )}
      {stop && stop.notes.length > 0 && (
        <ul className="queue-notes" data-testid="queue-notes">
          {stop.notes.map((note) => (
            <li key={note.id}>{note.text}</li>
          ))}
        </ul>
      )}
      {props.findings.map((finding) => (
        <p className="queue-action" key={finding.code + finding.message} data-testid="queue-finding">
          {finding.message}
        </p>
      ))}
      {fixable > 0 && (
        <details className="queue-fixable" data-testid="queue-fixable">
          <summary>
            {fixable} {fixable === 1 ? "finding an agent can fix" : "findings an agent can fix"}
          </summary>
          <ul>
            {fixes.map((fix) => (
              <li key={`${fix.asset}/${fix.stage}/${fix.code}/${fix.command}`}>
                <code>{fix.command}</code> <button onClick={() => void navigator.clipboard?.writeText(fix.command)}>Copy</button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
