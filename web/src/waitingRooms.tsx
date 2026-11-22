// The rooms of a district that wait for a Source (ticket 0351, spec §11). Which rooms wait, what to paint and what the image comes
// back as is `to-paint`'s; filing it is `import`, `extend add` and `inbox`. Nothing here decides which room is which or what a
// file name means.

import { useEffect, useRef, useState } from "react";
import { call, callWithFile, fileUrl, type Envelope } from "./api";
import { FindingList } from "./components";

// `to-paint` writes into a folder; the file route serves only `.kiripix/previews/`, so that's where the view asks it to write.
const PAINT_OUT = ".kiripix/previews/to-paint";

interface PaintRoom {
  asset: string;
  number: number;
  what: "prompt" | "canvas" | "done";
  files: string[];
  sides: string[];
  return_name: string | null;
  next: string | null;
}

interface Unready {
  asset: string;
  code: string;
  reason: string;
  fix: string | null;
}

interface ToPaintData {
  folder: string;
  rooms: PaintRoom[];
  unready: Unready[];
}

interface InboxFile {
  file: string;
  outcome: string;
  asset: string | null;
  action: string | null;
  variant: string | null;
  piece: string | null;
  candidates: string[];
  code: string | null;
}

interface InboxData {
  folder: string;
  imported: number;
  left: number;
  files: InboxFile[];
  lone_variants: { asset: string; variant: string; pick: string }[];
}

type Work = <T>(label: string, action: () => Promise<Envelope<T>>) => Promise<Envelope<T> | null>;

export function WaitingRooms(props: {
  glob: string;
  refreshes: number;
  imageVersion: number;
  work: Work; // one Command through the App's queue of actions
  onOpen: (asset: string, stage: string | null) => void;
}) {
  const { glob, refreshes, work } = props;
  const [paint, setPaint] = useState<{ glob: string; value: Envelope<ToPaintData> } | null>(null);
  const [inbox, setInbox] = useState<Envelope<InboxData> | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const asked = useRef(0);

  useEffect(() => {
    const ticket = ++asked.current;
    call<ToPaintData>("to-paint", { match: glob, out: PAINT_OUT })
      .then((value) => {
        if (ticket === asked.current) setPaint({ glob, value });
      })
      .catch(() => undefined);
  }, [glob, refreshes]);

  useEffect(() => {
    setInbox(null);
    setCopied(null);
    setNote(null);
  }, [glob]);

  const shown = paint?.glob === glob ? paint.value.data : null;
  const rooms = shown?.rooms ?? [];
  const unready = shown?.unready ?? [];

  async function copyPrompt(room: PaintRoom) {
    const response = await fetch(fileUrl(`${shown!.folder}/${room.files[0]}`, refreshes));
    await navigator.clipboard.writeText(await response.text());
    setCopied(room.asset);
  }

  // A drop on a tile is `inbox --file` into that room, with the sides `to-paint` gave it: `inbox` decides whether that is an
  // import or a piece to join, and writes the canvas record a piece needs, as it does for a file named for the room.
  async function drop(asset: string, room: PaintRoom | null, files: File[]) {
    setOver(null);
    const file = files[0];
    if (!file) return;
    setNote(null);
    const result = await work(`Filing ${file.name} into ${asset}`, () =>
      callWithFile<InboxData>("inbox", { asset, sides: room?.sides ?? [] }, "file", file),
    );
    if (result && !result.ok) setNote(result.findings[0]?.message ?? `${asset}: refused`);
  }

  async function checkInbox() {
    setNote(null);
    const result = await work("Checking the inbox", () => call<InboxData>("inbox", {}));
    if (result) setInbox(result);
  }

  const lost = unready.length + rooms.length === 0;
  return (
    <section className="waiting" data-testid="waiting" aria-label="Rooms waiting for a Source">
      <div className="district-bar">
        <h2>Waiting for a Source</h2>
        <button data-testid="inbox-check" onClick={() => void checkInbox()} title="File the images in the inbox folder by their names">
          Check the inbox
        </button>
      </div>
      {lost && (
        <p className="hint" data-testid="waiting-none">
          No room waits for a Source.
        </p>
      )}
      {note && (
        <p className="hint" data-testid="waiting-note" role="alert">
          {note}
        </p>
      )}
      <div className="waiting-grid">
        {rooms.map((room) => (
          <div
            key={room.asset}
            className={`waiting-tile${over === room.asset ? " over" : ""}`}
            data-testid={`waiting-${room.asset}`}
            data-what={room.what}
            onDragOver={(event) => {
              if (room.what === "done" || !event.dataTransfer.types.includes("Files")) return;
              event.preventDefault();
              setOver(room.asset);
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(event) => {
              if (room.what === "done") return;
              event.preventDefault();
              void drop(room.asset, room, [...event.dataTransfer.files]);
            }}
          >
            <strong>{room.asset}</strong>
            {room.what === "done" ? (
              <>
                <span className="hint">Its joined image is big enough.</span>
                <button className="link" data-testid={`waiting-open-room-${room.asset}`} onClick={() => props.onOpen(room.asset, "source")}>
                  Open room
                </button>
              </>
            ) : (
              <>
                <span className="hint">{room.what === "canvas" ? `mid-extend: paint the canvas (${room.sides.join(", ")})` : "no Source yet"}</span>
                <span className="waiting-actions">
                  <button data-testid={`waiting-copy-${room.asset}`} onClick={() => void copyPrompt(room)}>
                    {copied === room.asset ? "Copied" : "Copy prompt"}
                  </button>
                  {room.what === "canvas" && room.files[1] && (
                    <a
                      className="button"
                      data-testid={`waiting-canvas-${room.asset}`}
                      href={fileUrl(`${shown!.folder}/${room.files[1]}`, refreshes)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open canvas
                    </a>
                  )}
                </span>
                <span className="hint">
                  Save the result as <code data-testid={`waiting-name-${room.asset}`}>{room.return_name}</code>
                </span>
                <span className="hint">Drop the image here</span>
              </>
            )}
          </div>
        ))}
        {unready.map((one) => (
          <div
            key={one.asset}
            className={`waiting-tile${over === one.asset ? " over" : ""}`}
            data-testid={`waiting-${one.asset}`}
            data-what="unready"
            data-code={one.code}
            onDragOver={(event) => {
              if (!event.dataTransfer.types.includes("Files")) return;
              event.preventDefault();
              setOver(one.asset);
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(event) => {
              event.preventDefault();
              void drop(one.asset, null, [...event.dataTransfer.files]);
            }}
          >
            <strong>{one.asset}</strong>
            <span className="hint" data-testid={`waiting-reason-${one.asset}`}>
              {one.reason}
            </span>
            {one.fix && <code>{one.fix}</code>}
            <span className="hint">Drop the image here</span>
          </div>
        ))}
      </div>
      <p className="hint">Drop an image on a room, or put images in the inbox folder named as shown and check the inbox.</p>
      {inbox && (
        <div className="district-outcome" data-testid="inbox-result">
          <h2>Inbox</h2>
          {inbox.data && (
            <>
              <p data-testid="inbox-summary">
                {inbox.data.imported} imported, {inbox.data.left} left in {inbox.data.folder}
              </p>
              <ul>
                {inbox.data.files.map((file) => (
                  <li key={file.file} data-testid={`inbox-file-${file.file}`} data-outcome={file.outcome}>
                    {file.file}: {file.outcome}
                    {file.asset ? ` to ${file.asset}` : ""}
                    {file.candidates.length > 0 ? ` (${file.candidates.join(", ")})` : ""}
                  </li>
                ))}
              </ul>
              {inbox.data.lone_variants.length > 0 && (
                <ul data-testid="inbox-lone">
                  {inbox.data.lone_variants.map((lone) => (
                    <li key={lone.asset}>
                      <button className="link" data-testid={`inbox-lone-${lone.asset}`} onClick={() => props.onOpen(lone.asset, "source")}>
                        {lone.asset}
                      </button>{" "}
                      has one Variant, {lone.variant}, to pick
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {inbox.findings.length > 0 && (
            <FindingList
              findings={inbox.findings}
              onJump={(finding) => finding.position?.asset && props.onOpen(finding.position.asset, finding.position.stage ?? null)}
              testid="inbox-findings"
            />
          )}
        </div>
      )}
    </section>
  );
}
