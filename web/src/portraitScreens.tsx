// The portrait's screens (ticket 0245, spec §6.7, §11): the emotion strip, flip in place, and the `face` region.
//
// Every Stage after `source` is a shared screen rendered from `describe`; what is hand-written is the strip (the set's emotions
// with their Picks, an import-and-pick, a declaration), the flip tool that lays the selected emotion over the neutral, and the
// `face` region on `register`, drawn with the Looks' brush and polygon (`MaskTool`). Each gesture is one `decide`, and no
// computing is done here: the region shown is the file the Stage wrote, the boxes are the findings' `data`.

import { useEffect, useRef, useState, type RefObject } from "react";
import { fileUrl, type Finding, type ShowData, type StageDetail } from "./api";
import { MAX_RADIUS, MaskTool, MIN_RADIUS, tintOf } from "./maskTool";
import { isTyping, type PixelCanvas } from "./pixelCanvas";
import { FlipTool, type ShimmerBox } from "./portraitTool";
import { loadMask, type MaskPixels } from "./walkTest";

export const PORTRAIT_KIND = "portrait";
export const FACE_STAGE = "register";
export const FACE_DECISION = "face";
export const SHIMMER_STAGE = "finish";
export const EMOTION_DECISION = "emotion";
const FACE = "face";
const NEUTRAL = "neutral";
const IMAGE_STAGES = ["finish", "palette", "fit", "register", "cutout", "source"]; // furthest built first

// A Stage's image of one emotion: `emotions/<id>.png` beside the Stage's own image (the layout ticket 0243 records). `show` doesn't
// list these files (`outputs` is the folder's top level), so whether it exists is known only when it loads.
export function emotionImage(detail: StageDetail | undefined, id: string): string | null {
  const own = detail?.image;
  return own ? `${own.slice(0, own.lastIndexOf("/"))}/emotions/${id}.png` : null;
}

function aboutEmotion(finding: Finding, id: string): boolean {
  return finding.data?.emotion === id;
}

function worst(findings: Finding[]): string {
  if (findings.some((finding) => finding.severity === "error")) return "error";
  return findings.length > 0 ? "warning" : "ok";
}

// What an emotion's thumbnail shows: the furthest built Stage's image of it, else its picked Variant.
function thumbnailSources(show: ShowData, id: string | null): string[] {
  const built = IMAGE_STAGES.map((name) => {
    const stage = show.stages.find((entry) => entry.stage === name);
    return id === null ? (stage?.image ?? null) : emotionImage(stage, id);
  }).filter((path): path is string => path !== null);
  const own = id === null ? { variants: show.variants, picked: show.picked } : show.emotions?.find((entry) => entry.emotion === id);
  const picked = own?.variants.find((variant) => variant.name === own.picked)?.file;
  return [...built, ...(picked ? [picked] : [])];
}

// Pixel art at a whole-number scale: up when it is small, down by a whole divisor when it is large; never smoothed.
function Thumb(props: { sources: string[]; version: number; box: number; label: string }) {
  const [tried, setTried] = useState(0);
  const [scale, setScale] = useState(1);
  const source = props.sources[tried];
  if (!source) return <span className="state-thumb empty" />;
  return (
    <img
      className="state-thumb"
      alt={props.label}
      src={fileUrl(source, props.version)}
      style={{ width: "auto", height: "auto", zoom: scale }}
      onLoad={(event) => {
        const { naturalWidth: w, naturalHeight: h } = event.currentTarget;
        const longer = Math.max(w, h, 1);
        setScale(longer <= props.box ? Math.floor(props.box / longer) : 1 / Math.ceil(longer / props.box));
      }}
      onError={() => setTried((n) => n + 1)}
    />
  );
}

export function EmotionStrip(props: {
  show: ShowData;
  emotion: string | null; // null: the neutral
  findings: Finding[];
  imageVersion: number;
  disabled: boolean;
  onSelect: (emotion: string | null) => void;
  declare: (id: string) => void;
  importAndPick: (file: File, emotion: string) => void;
}) {
  const { show, emotion, findings, imageVersion, disabled } = props;
  const [id, setId] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const entries = [
    { id: null as string | null, name: NEUTRAL, status: show.picked ? `Source ${show.picked.slice(0, 8)}` : "no Source picked", mine: [] as Finding[] },
    ...(show.emotions ?? []).map((entry) => ({
      id: entry.emotion as string | null,
      name: entry.emotion,
      status: !entry.picked
        ? "no image picked"
        : entry.current
          ? `Variant ${entry.picked.slice(0, 8)}`
          : "made on another Source",
      mine: findings.filter((finding) => aboutEmotion(finding, entry.emotion)),
    })),
  ];
  const valid = id.trim().length > 0; // the ID's rules are `decide`'s: it refuses a bad or a taken one with its finding

  return (
    <section className="state-strip" data-testid="emotion-strip" aria-label="Emotions">
      <h2>Emotions</h2>
      <div className="state-list" role="group" aria-label="Emotion">
        {entries.map((entry, index) => (
          <button
            key={entry.name}
            className="state-card"
            data-testid={`emotion-${entry.name}`}
            data-findings={worst(entry.mine)}
            aria-pressed={entry.id === emotion}
            title={entry.mine.map((finding) => finding.code).join(", ")}
            onClick={() => props.onSelect(entry.id)}
          >
            <Thumb sources={thumbnailSources(show, entry.id)} version={imageVersion} box={96} label={`Emotion ${entry.name}`} />
            <span>
              {entry.name}
              {index === 0 && " (Source)"}
            </span>
            <span className="hint" data-testid={`emotion-${entry.name}-pick`}>
              {entry.status}
              {entry.mine.length > 0 && ` · ${entry.mine.length} finding(s)`}
            </span>
          </button>
        ))}
      </div>
      {emotion && (
        <div className="decisions">
          <button data-testid="emotion-import" disabled={disabled} onClick={() => input.current?.click()}>
            Import an image for {emotion}
          </button>
          <input
            ref={input}
            data-testid="emotion-import-input"
            type="file"
            accept="image/png,image/jpeg"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) props.importAndPick(file, emotion);
              event.target.value = "";
            }}
          />
        </div>
      )}
      <fieldset disabled={disabled} className="state-declare">
        <legend>Declare an emotion</legend>
        <label>
          ID
          <input data-testid="emotion-id" value={id} placeholder="happy" onChange={(event) => setId(event.target.value)} />
        </label>
        <button
          data-testid="emotion-declare"
          disabled={!valid}
          onClick={() => {
            props.declare(id);
            setId("");
          }}
        >
          Declare
        </button>
      </fieldset>
    </section>
  );
}

type Tool = "brush" | "erase" | "polygon" | "polygon-erase";
const TOOLS: { name: Tool; key: string; label: string; hint: string }[] = [
  { name: "brush", key: "b", label: "Brush", hint: "Drag to add to the face region." },
  { name: "erase", key: "e", label: "Erase", hint: "Drag to take from the face region." },
  { name: "polygon", key: "g", label: "Polygon", hint: "Click the corners; click the first point or press Enter to close and fill. Backspace removes the last point, Esc drops it." },
  { name: "polygon-erase", key: "x", label: "Erase polygon", hint: "Click the corners; click the first point or press Enter to close and clear." },
];

async function sizeOf(url: string): Promise<[number, number]> {
  const image = new Image();
  image.src = url;
  await image.decode();
  return [image.naturalWidth, image.naturalHeight];
}

// Flip in place on every Stage that has the set's images, and the `face` region on `register`.
export function PortraitPanel(props: {
  canvas: RefObject<PixelCanvas | null>;
  show: ShowData;
  stage: string;
  detail: StageDetail;
  emotion: string | null;
  onSelect: (emotion: string | null) => void;
  findings: Finding[];
  imageVersion: number;
  disabled: boolean;
  rebuild: boolean;
  onRebuild: (rebuild: boolean) => void;
  decide: (decision: string, data: Record<string, unknown>, settled?: () => void) => void;
}) {
  const { canvas, show, stage, detail, imageVersion, disabled } = props;
  const faceStage = stage === FACE_STAGE;
  const emotions = (show.emotions ?? []).map((entry) => entry.emotion);
  const target = props.emotion ?? emotions[0] ?? null; // the neutral is what is under the flip
  const file = target ? emotionImage(detail, target) : null;
  const [flipped, setFlipped] = useState(false);
  const [loaded, setLoaded] = useState<string | null>(null); // the emotion image that loaded on this Stage
  const [tool, setTool] = useState<Tool>("polygon");
  const [radius, setRadius] = useState(2);
  const [opacity, setOpacity] = useState(40);
  const flip = useRef<FlipTool>(new FlipTool());
  const painter = useRef<MaskTool | null>(null);
  const latest = useRef(props);
  latest.current = props;

  const faceFile = detail.outputs.find((path) => path.endsWith("/face.png")) ?? null;
  const shimmer =
    stage === SHIMMER_STAGE && target
      ? ((props.findings.find((finding) => finding.code === "portrait.shimmer" && aboutEmotion(finding, target))?.data?.boxes ?? []) as ShimmerBox[])
      : [];
  const shimmerText = JSON.stringify(shimmer);

  // The tools, made once: the emotion over the neutral, and (on `register`) the face region tinted over it.
  useEffect(() => {
    const tools: (FlipTool | MaskTool)[] = [flip.current];
    if (faceStage) {
      const painting = new MaskTool(
        {
          stroke(on, erase, size, points) {
            const done = painter.current?.addMark({ kind: "stroke", mask: on, erase, radius: size, points });
            latest.current.decide(FACE_DECISION, { points, radius: size, ...(erase ? { erase } : {}) }, done);
          },
          polygon(on, erase, points) {
            const done = painter.current?.addMark({ kind: "polygon", mask: on, erase, points });
            latest.current.decide(FACE_DECISION, { points, ...(erase ? { erase } : {}) }, done);
          },
          point() {},
          async preview() {
            return null;
          },
        },
        () => canvas.current?.redraw(),
      );
      painter.current = painting;
      tools.push(painting);
    }
    canvas.current?.setTools(tools);
    return () => {
      painter.current?.destroy();
      painter.current = null;
      canvas.current?.setTools([]);
    };
  }, [canvas, faceStage]);

  useEffect(() => {
    flip.current.flipped = flipped;
    flip.current.emotion = target ?? "";
    flip.current.boxes = JSON.parse(shimmerText) as ShimmerBox[];
    canvas.current?.redraw();
  }, [canvas, flipped, target, shimmerText]);

  // The emotion's image on this Stage, read again when pictures change.
  useEffect(() => {
    let live = true;
    flip.current.image = null;
    setLoaded(null);
    canvas.current?.redraw();
    if (!file) return;
    const image = new Image();
    image.onload = () => {
      if (!live) return;
      flip.current.image = image;
      setLoaded(file);
      canvas.current?.redraw();
    };
    image.src = fileUrl(file, imageVersion);
    return () => {
      live = false;
    };
  }, [canvas, file, imageVersion]);

  useEffect(() => {
    const painting = painter.current;
    if (!painting) return;
    painting.setTool(tool);
    painting.mask = FACE;
    painting.radius = radius;
    painting.opacity = opacity / 100;
    canvas.current?.redraw();
  }, [canvas, tool, radius, opacity, faceStage]);

  // The region the Stage wrote, in the neutral cutout's pixels: the file itself, nothing computed here.
  useEffect(() => {
    const painting = painter.current;
    if (!faceStage || !painting) return;
    let live = true;
    void (async () => {
      let pixels: MaskPixels;
      if (faceFile) {
        pixels = await loadMask(fileUrl(faceFile, imageVersion));
      } else if (detail.image) {
        const [width, height] = await sizeOf(fileUrl(detail.image, imageVersion));
        pixels = { width, height, set: new Uint8Array(width * height) };
      } else {
        return;
      }
      if (!live) return;
      painting.setMasks([{ name: FACE, pixels }]);
      canvas.current?.redraw();
    })().catch(() => undefined);
    return () => {
      live = false;
    };
  }, [canvas, faceStage, faceFile, detail.image, imageVersion]);

  // `V` flips, `1` to `9` pick an emotion, and on `register` the letters pick a tool and `[ ]` the brush size.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      const chosen = faceStage ? TOOLS.find((entry) => entry.key === key) : undefined;
      if (key === "v") setFlipped((now) => !now);
      else if (chosen) setTool(chosen.name);
      else if (key === "0") latest.current.onSelect(null);
      else if (/^[1-9]$/.test(key)) {
        const one = (latest.current.show.emotions ?? [])[Number(key) - 1];
        if (one) latest.current.onSelect(one.emotion);
      } else if (faceStage && event.key === "[") setRadius((size) => Math.max(MIN_RADIUS, size - 1));
      else if (faceStage && event.key === "]") setRadius((size) => Math.min(MAX_RADIUS, size + 1));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [faceStage]);

  const active = TOOLS.find((entry) => entry.name === tool)!;
  const hasFace = faceFile !== null;
  return (
    <fieldset disabled={disabled} className="mask-form" data-testid="portrait-panel">
      {emotions.length > 0 && (
        <>
          <h2>Flip</h2>
          <div className="tools" role="group" aria-label="Flip">
            <button data-testid="flip-neutral" aria-pressed={!flipped} onClick={() => setFlipped(false)}>
              Neutral
            </button>
            <button data-testid="flip-emotion" aria-pressed={flipped} disabled={loaded !== file || !file} onClick={() => setFlipped(true)}>
              {target ?? "Emotion"}
            </button>
          </div>
          <p className="hint" data-testid="flip-hint">
            <kbd>V</kbd> flips {target ?? "the emotion"} over the neutral, in place, at the canvas's size; <kbd>1</kbd> to <kbd>9</kbd> pick the emotion.
            {loaded !== file && target && ` ${target} has no image on this Stage yet.`}
            {stage === SHIMMER_STAGE && shimmer.length > 0 && ` The red dashed boxes are where ${target} differs from the neutral outside the face.`}
          </p>
        </>
      )}
      {faceStage && (
        <>
          <h2>Face region</h2>
          <p className="hint" data-testid="face-summary">
            {hasFace ? "A face region is drawn." : "No face region is drawn."} Draw it on the neutral, round everything meant to change.
          </p>
          <div className="tools" role="group" aria-label="Tool">
            {TOOLS.map((entry) => (
              <button key={entry.name} data-testid={`tool-${entry.name}`} aria-pressed={tool === entry.name} title={`${entry.label} (${entry.key.toUpperCase()})`} onClick={() => setTool(entry.name)}>
                {entry.label} <kbd>{entry.key.toUpperCase()}</kbd>
              </button>
            ))}
          </div>
          <p className="hint">{active.hint}</p>
          <div className="param">
            <label htmlFor="face-radius">Brush size</label>
            <input id="face-radius" data-testid="face-radius" type="number" min={MIN_RADIUS} max={MAX_RADIUS} value={radius} onChange={(event) => setRadius(Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.trunc(Number(event.target.value)) || 0)))} />
          </div>
          <div className="param">
            <label htmlFor="face-opacity">Overlay opacity</label>
            <input id="face-opacity" data-testid="face-opacity" type="range" min={0} max={100} value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} />
          </div>
          <label className="toggle">
            <input type="checkbox" data-testid="face-rebuild" checked={props.rebuild} onChange={(event) => props.onRebuild(event.target.checked)} />
            <span className="swatch" style={{ background: tintOf(0) }} /> Register again after each edit
          </label>
          <p className="hint">
            <kbd>[</kbd> <kbd>]</kbd> change the brush size, <kbd>Z</kbd> zooms, hold <kbd>Space</kbd> and drag to pan, <kbd>Enter</kbd> closes a polygon,{" "}
            <kbd>Ctrl+Z</kbd> undoes.
          </p>
        </>
      )}
    </fieldset>
  );
}
