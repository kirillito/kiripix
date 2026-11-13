import { useCallback, useEffect, useRef, useState } from "react";
import {
  call,
  callWithFile,
  cancelJob,
  events,
  fileUrl,
  type DescribeData,
  type Envelope,
  type Finding,
  type NextData,
  type Scalar,
  type ShowData,
  type StageDescription,
  type StatusData,
} from "./api";
import {
  AssetList,
  CanvasView,
  FilterBar,
  FindingList,
  ParamControl,
  pressing,
  readable,
  StageBar,
  StatusBoard,
  VariantGrid,
  type Filter,
} from "./components";
import { isTyping, type PixelCanvas } from "./pixelCanvas";
import { MASKS_STAGE, MasksPanel } from "./maskScreen";
import { ambiguousCells } from "./markerTool";
import { ABOVE_DECISION, PLACE_DECISION, PlacePanel, REACH_STAGE, ReachPanel } from "./roomScreens";
import { FOOTPRINT_DECISION, FootprintPanel } from "./propScreens";
import { LAYERS_DECISION, LAYERS_STAGE, LayersPanel } from "./layerScreen";
import { layerIdOf } from "./sortView";
import { CHARACTER_KIND, CHARACTER_SCREENS, CharacterScreen, type ImportRole } from "./characterScreens";
import { SPRITE_FRAMES_STAGE, SPRITE_KIND, SpriteFramesScreen } from "./spriteScreens";
import { FRAME_STAGES, FrameScreen, frameOf, type FrameFocus } from "./frameScreen";
import { WorkStrip, type Working } from "./workStrip";

const PICK = "pick"; // the Decision that makes a Stage's screen the Variant grid
const REFRESH_DELAY_MS = 100; // one refresh for a burst of "changed" events

// An action the Owner started, from the click until its result has landed (ticket 0083).
interface Work {
  id: number;
  label: string;
  kind: string | null;
  since: number | null; // set when it reaches the front of the queue
}

interface Selected {
  status: StatusData | null;
  show: ShowData | null;
  next: NextData | null;
  checks: Finding[];
  problems: Finding[]; // why the Project or the Asset can't be read
  refreshes: number;
}

function distinct(findings: Finding[]): Finding[] {
  const seen = new Set<string>();
  return findings.filter((finding) => {
    const key = `${finding.code} ${finding.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function initialParam(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}

export function App() {
  const [asset, setAsset] = useState(initialParam("asset"));
  const [stage, setStage] = useState(initialParam("stage"));
  const [data, setData] = useState<Selected>({
    status: null,
    show: null,
    next: null,
    checks: [],
    problems: [],
    refreshes: 0,
  });
  const [imageVersion, setImageVersion] = useState(0);
  const [refusals, setRefusals] = useState(0);
  const [recipes, setRecipes] = useState<Record<string, StageDescription[]>>({});
  const [filter, setFilter] = useState<Filter>("all");
  const [notice, setNotice] = useState<Finding[]>([]);
  const [job, setJob] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState<string | null>(null);
  const [progress, setProgressText] = useState<string | null>(null);
  const [fraction, setFraction] = useState<number | null>(null);
  const [works, setWorks] = useState<Work[]>([]);
  const [reading, setReading] = useState<{ label: string; since: number } | null>({
    label: asset ? `Opening ${asset}` : "Reading the Project",
    since: Date.now(),
  });
  const setProgress = useCallback((message: string | null, part: number | null = null) => {
    setProgressText(message);
    setFraction(part);
  }, []);
  const [connected, setConnected] = useState(true);
  const [gameFrame, setGameFrame] = useState(false);
  const [rebuild, setRebuild] = useState(true);
  const [layersRebuild, setLayersRebuild] = useState(false); // each rebuild is a Runner call, so it's the Owner's to ask for
  const [focusLayer, setFocusLayer] = useState<{ layer: string; count: number } | null>(null); // a `layer.no_ysort` jump
  const [focusFrame, setFocusFrame] = useState<FrameFocus | null>(null); // a frame finding's jump
  const [, setRefocus] = useState(0); // one more render, to run the focus effect when a finding is on this Stage
  const canvas = useRef<PixelCanvas>(null);

  // One refresh at a time, in order, and one more if something changed meanwhile: what shows is never older than a change.
  const selection = useRef(asset);
  selection.current = asset;
  const refreshing = useRef<"idle" | "busy" | "again">("idle");
  const refresh = useCallback(async () => {
    if (refreshing.current !== "idle") {
      refreshing.current = "again";
      return;
    }
    do {
      refreshing.current = "busy";
      const chosen = selection.current;
      try {
        const status = await call<StatusData>("status", {});
        let [show, next, checks]: [ShowData | null, NextData | null, Finding[]] = [null, null, []];
        const problems = [...status.findings];
        if (chosen) {
          const shown = await call<ShowData>("show", { asset: chosen });
          show = shown.data;
          problems.push(...shown.findings);
          next = (await call<NextData>("next", { asset: chosen })).data;
          checks = (await call<unknown>("check", { asset: chosen })).findings;
        }
        if (chosen === selection.current) {
          setData((before) => ({
            status: status.data,
            show,
            next,
            checks,
            problems: distinct(problems),
            refreshes: before.refreshes + 1,
          }));
        }
        setConnected(true);
      } catch {
        setConnected(false);
      }
    } while ((refreshing.current as string) === "again");
    refreshing.current = "idle";
    setReading(null);
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    const close = events({
      onChange: (paths) => {
        // Only a changed image is fetched again: the browser reuses an image URL it has already shown.
        if (!paths || paths.some((path) => path.endsWith(".png"))) setImageVersion((version) => version + 1);
        window.clearTimeout(timer);
        timer = window.setTimeout(() => void refresh(), REFRESH_DELAY_MS);
      },
      onProgress: setProgress,
      onLost: () => setConnected(false),
    });
    return () => {
      window.clearTimeout(timer);
      close();
    };
  }, [refresh, setProgress]);

  useEffect(() => {
    void refresh();
  }, [asset, refresh]);

  const show = data.show?.asset === asset ? data.show : null;
  const kind = show?.kind;
  useEffect(() => {
    if (!kind || recipes[kind]) return;
    call<DescribeData>("describe", { target: kind })
      .then((result) => {
        const stages = result.data?.kinds[0]?.stages;
        if (stages) setRecipes((known) => ({ ...known, [kind]: stages }));
      })
      .catch(() => setConnected(false)); // The next refresh asks again.
  }, [kind, recipes, data.refreshes]);

  // An Asset opens on what it needs next: `next` says which Stage. After that the view stays where the Owner put it,
  // whatever an agent or a Run does.
  const next = data.next?.asset === asset ? data.next : null;
  const current = stage ?? next?.stage ?? show?.stages[0]?.stage ?? null;
  useEffect(() => {
    if (stage === null && show && current) setStage(current);
  }, [stage, show, current]);

  useEffect(() => {
    const query = new URLSearchParams();
    if (asset) query.set("asset", asset);
    if (asset && current) query.set("stage", current);
    const search = query.toString();
    history.replaceState(null, "", window.location.pathname + (search ? `?${search}` : ""));
  }, [asset, current]);

  const description = kind ? recipes[kind]?.find((entry) => entry.name === current) : undefined;
  const detail = show?.stages.find((entry) => entry.stage === current);
  const isSource = description?.decisions.some((decision) => decision.name === PICK) ?? false;
  const isPlace = description?.decisions.some((decision) => decision.name === PLACE_DECISION) ?? false;
  const isMasks =
    current === MASKS_STAGE && (description?.decisions.some((decision) => decision.name === "brush") ?? false);
  const isLayers =
    current === LAYERS_STAGE && (description?.decisions.some((decision) => decision.name === LAYERS_DECISION) ?? false);
  const isReach = current === REACH_STAGE && show?.kind === "room";
  const isCharacterScreen =
    show?.kind === CHARACTER_KIND && current !== null && CHARACTER_SCREENS.includes(current) && description !== undefined;
  const hasFrames = show?.kind === CHARACTER_KIND || show?.kind === SPRITE_KIND;
  const isFrames = hasFrames && current !== null && FRAME_STAGES.includes(current) && description !== undefined;
  const isSpriteFrames = show?.kind === SPRITE_KIND && current === SPRITE_FRAMES_STAGE && description !== undefined;
  const isPivot = show?.kind === SPRITE_KIND && current === "fit";
  const isFootprint = description?.decisions.some((decision) => decision.name === FOOTPRINT_DECISION) ?? false;

  // Each user action is one Command (a Mask edit may add a `run`, ADR 0006); its findings show until the next action. They
  // go one at a time, in the order they were made: a Run straight after a `set` must see that `set`, not find its lock held.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const workIds = useRef(0);
  const perform = useCallback(
    <T,>(
      action: () => Promise<Envelope<T>>,
      label = "Working",
      kind: string | null = null,
      settled?: () => void,
    ): Promise<void> => {
      // Registered at once, so the strip and the marks show before the server has answered; it stays until its result landed.
      const id = ++workIds.current;
      setWorks((now) => [...now, { id, label, kind, since: null }]);
      const done = queue.current.then(async () => {
        setWorks((now) => now.map((work) => (work.id === id ? { ...work, since: Date.now() } : work)));
        try {
          const result = await action();
          setNotice(result.findings);
          setConnected(true);
          await refresh();
        } catch {
          setConnected(false);
        } finally {
          setWorks((now) => now.filter((work) => work.id !== id));
          settled?.();
        }
      });
      queue.current = done;
      return done;
    },
    [refresh],
  );

  // A Run holds the Asset's lock, and what is done meanwhile would be refused or make its output stale at once.
  const busy = job !== null;
  const setParam = (name: string, value: Scalar) =>
    void perform(async () => {
      const result = await call("set", { asset, stage: current, assignments: [`${name}=${value}`] });
      if (!result.ok) setRefusals((count) => count + 1); // The control goes back to the value that stands.
      return result;
    }, `Setting ${name}`);
  const decideMarker = useCallback(
    (marker: Record<string, unknown>) => {
      const decision = JSON.stringify({ decision: PLACE_DECISION, data: marker });
      void perform(() => call("decide", { asset, stage: current, decision }), "Placing a marker");
    },
    [asset, current, perform],
  );
  const decideAbove = useCallback(
    (layer: string, above: boolean) => {
      const decision = JSON.stringify({ decision: ABOVE_DECISION, data: { layer, above } });
      void perform(() => call("decide", { asset, stage: current, decision }), "Setting the sort side");
    },
    [asset, current, perform],
  );
  const decideFootprint = useCallback(
    (footprint: Record<string, unknown>) => {
      const decision = JSON.stringify({ decision: FOOTPRINT_DECISION, data: footprint });
      void perform(() => call("decide", { asset, stage: current, decision }), "Setting the footprint");
    },
    [asset, current, perform],
  );
  // A Mask edit shows once the Stage has run again, so with "rebuild" on the same action runs it, as a refresh would.
  // Only a `click` asks for a Runner's result, hence `rerun` for it alone: no other edit may re-run a pinned call (ADR 0002).
  // It can be cancelled, but it doesn't make the screen busy: the queue keeps quick strokes in order, and none is dropped.
  const rebuilt = useCallback(
    async <T,>(result: Envelope<T>, rerun = false, force = false): Promise<Envelope<unknown>> => {
      // `force`: a removed Layer is taken out by a plain `run layers`, with no rerun and no accept (ticket 0091).
      if (!(force || (isMasks ? rebuild : isLayers && layersRebuild)) || !result.ok) return result;
      const id = crypto.randomUUID();
      setRebuilding(id);
      try {
        const ran = await call("run", { asset, stage: current, rerun }, id);
        return { ...ran, findings: [...result.findings, ...ran.findings] };
      } finally {
        setRebuilding(null);
        setProgress(null);
      }
    },
    [asset, current, isMasks, isLayers, rebuild, layersRebuild],
  );
  const decideMask = useCallback(
    (name: string, data: Record<string, unknown>, settled?: () => void) => {
      const decision = JSON.stringify({ decision: name, data });
      const into = String(data.layer ?? data.mask ?? "");
      const verbs: Record<string, string> = {
        trim: "Trimming",
        brush: data.erase ? "Erasing" : "Painting",
        flood: "Flooding",
        click: "Clicking into",
        border: "Bordering",
        remove: "Removing",
      };
      const label =
        name === "click" && isLayers
          ? data.positive === false
            ? `Taking from ${into}`
            : `Lifting into ${into}`
          : `${verbs[name] ?? "Deciding on"} ${into}`;
      void perform(
        async () => rebuilt(await call("decide", { asset, stage: current, decision }), name === "click", name === "remove" && isLayers),
        label,
        null,
        settled,
      );
    },
    [asset, current, isLayers, perform, rebuilt],
  );
  // A click on `fit` is one `pivot` Decision; `fit` is then run again at once so the frame shows it (no Runner is called), as a
  // Mask edit does (ADR 0006). With no Direction the Decision is every Direction's.
  const decidePivot = useCallback(
    (x: number, y: number, direction: string, all: boolean) => {
      const decision = JSON.stringify({ decision: "pivot", data: all ? { x, y } : { x, y, direction } });
      void perform(
        async () => rebuilt(await call("decide", { asset, stage: current, decision }), false, true),
        all ? "Setting the pivot of every Direction" : `Setting the pivot of ${direction}`,
      );
    },
    [asset, current, perform, rebuilt],
  );
  const importMask = useCallback(
    (file: File) => void perform(async () => rebuilt(await callWithFile("mask-import", { asset }, "png", file)), "Importing a Mask image"),
    [asset, perform, rebuilt],
  );
  const importPlate = useCallback(
    (file: File) => void perform(async () => rebuilt(await callWithFile("plate-import", { asset }, "png", file)), "Importing a Plate image"),
    [asset, perform, rebuilt],
  );
  const pick = useCallback(
    (variant: string) => {
      if (!busy) void perform(() => call("pick", { asset, variant }), "Picking a Variant");
    },
    [asset, busy, perform],
  );
  const importFiles = async (files: File[], role: ImportRole = "variant") => {
    for (const file of files) {
      await perform(() => callWithFile("import", { asset, role }, "file", file), `Importing ${file.name}`);
    }
  };
  // A character's Decisions (a `bone`, a `clip`): one `decide` each, nothing run after it.
  const decideCharacter = useCallback(
    (name: string, data: Record<string, unknown>, label: string) => {
      const decision = JSON.stringify({ decision: name, data });
      void perform(() => call("decide", { asset, stage: current, decision }), label);
    },
    [asset, current, perform],
  );
  const step = useCallback(
    (command: "undo" | "redo") => {
      if (!busy) void perform(
          async () => {
            // Undoing or redoing a remove changes which Layers there are, so `layers` is run again (never a rerun: a
            // Runner call still missing waits for the Owner). Every step on `layers` does it, because which Decision a
            // queued step undoes is only known once the steps before it have landed.
            const result = await call(command, { asset, stage: current });
            return rebuilt(result, false, isLayers || isPivot);
          },
          command === "undo" ? "Undoing" : "Redoing",
        );
    },
    [asset, busy, current, isLayers, isPivot, perform, rebuilt],
  );

  // The job exists once it reaches the front of the queue, and only then can it be cancelled.
  const run = async () => {
    const id = crypto.randomUUID();
    await perform(() => {
      setJob(id);
      return call("run", { asset }, id);
    }, `Running ${asset}`);
    setJob(null);
    setProgress(null);
  };
  // A stale or new Runner call is re-run only when the Owner says so (ADR 0002): `next` names it, and this button is that.
  const rerun = async () => {
    const id = crypto.randomUUID();
    await perform(() => {
      setJob(id);
      return call("run", { asset, stage: current, rerun: true }, id);
    }, `Re-running ${current}`);
    setJob(null);
    setProgress(null);
  };
  // One Accept at a time: it can't be cancelled, so a second press while it works would only be a second request.
  const accepting = works.some((work) => work.kind === "accept");
  const acceptingNow = useRef(false);
  const accept = () => {
    if (acceptingNow.current) return;
    acceptingNow.current = true;
    void perform(() => call("accept", { asset, stage: current }), `Accepting ${current}`, "accept").finally(() => {
      acceptingNow.current = false;
    });
  };

  const names = show?.stages.map((entry) => entry.stage) ?? [];
  const following = current ? names[names.indexOf(current) + 1] : undefined;

  const variants = show?.variants;
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTyping(event.target)) return;
      if ((event.ctrlKey || event.metaKey) && event.code === "KeyZ" && description?.decisions.length) {
        event.preventDefault();
        step(event.shiftKey ? "redo" : "undo");
      } else if (isSource && /^[1-9]$/.test(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const variant = variants?.[Number(event.key) - 1];
        if (variant) pick(variant.name);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [description, isSource, pick, step, variants]);

  function goHome() {
    setReading({ label: "Opening the room list", since: Date.now() });
    if (selection.current === null) void refresh();
    setAsset(null);
  }

  function open(assetId: string, stageName: string | null) {
    setReading({ label: `Opening ${assetId}`, since: Date.now() });
    if (assetId === selection.current) void refresh(); // the effect runs only when the Asset changes
    setAsset(assetId);
    setStage(stageName);
    setNotice([]);
    setFocusLayer(null);
    setFocusFrame(null);
  }

  // Children's effects run first, so the canvas has already started on the new Stage's image when this one focuses it.
  const jumpTo = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    if (jumpTo.current) canvas.current?.focus(jumpTo.current.x, jumpTo.current.y);
    jumpTo.current = null;
  });

  function jump(finding: Finding) {
    const { stage: where, x, y, width, height } = finding.position ?? {};
    // The canvas focuses one pixel: a box (an open edge) is focused at its middle.
    if (x != null && y != null) jumpTo.current = { x: x + Math.floor((width ?? 1) / 2), y: y + Math.floor((height ?? 1) / 2) };
    const cell = ambiguousCells(finding)?.cells[0]; // the first ambiguous cell, rather than the middle of its area
    if (cell) jumpTo.current = cell;
    const layer = finding.code === "layer.no_ysort" ? layerIdOf(finding.position?.file ?? "") : undefined;
    const framed = hasFrames ? frameOf(finding) : null;
    if (framed) setFocusFrame((before) => ({ ...framed, count: (before?.count ?? 0) + 1 }));
    if (layer) setFocusLayer((before) => ({ layer, count: (before?.count ?? 0) + 1 }));
    if (where && where !== current) setStage(where);
    else setRefocus((count) => count + 1);
  }

  const stageChecks = readable(
    data.checks.filter((finding) => (finding.position?.stage ?? current) === current),
    [],
    show?.stages,
  );
  const noticeShown = readable(notice, stageChecks, show?.stages);
  const problemsShown = readable(data.problems, [...stageChecks, ...noticeShown]);
  const wantsReview = detail?.status === "needs-review";
  const wantsRerun = next?.stage === detail?.stage && !!next?.command?.includes("--rerun");
  // The rig screen lists the Mixamo steps itself, so the panel doesn't say them twice.
  const stepsShown = isCharacterScreen && current === "rig" && !!next?.owner_action && next.stage === detail?.stage;
  const asking = pressing([...stageChecks, ...noticeShown, ...problemsShown]);
  const nextLine =
    next && next.stage === detail?.stage && next.owner_action
      ? next.owner_action
      : wantsReview
        ? "Look at the result, then accept it to go on."
        : asking?.owner_action;
  // Reach has no image of its own, and the Body walks on the mapped room that `place` is made on.
  const reachImage = isReach ? show?.stages.find((entry) => entry.stage === "place")?.input_image : null;
  const image = detail?.image ?? detail?.input_image ?? reachImage ?? null;
  const after = image ? fileUrl(image, imageVersion) : null;
  const before = detail?.image && detail.input_image ? fileUrl(detail.input_image, imageVersion) : null;

  // The strip: the action at the front of the queue, else the read in flight. The rest of the queue is the waiting count.
  const front = works.find((work) => work.since !== null) ?? works[0];
  const working: Working | null = front
    ? { label: front.label, since: front.since ?? Date.now(), waiting: works.length - 1, progress, fraction }
    : reading
      ? { label: reading.label, since: reading.since, waiting: 0, progress: null, fraction: null }
      : null;
  useEffect(() => {
    if (works.length === 0) setProgress(null);
  }, [works.length, setProgress]);

  const cancellable = job ?? rebuilding;
  const primary = cancellable ? (
    <button className="primary" data-testid="cancel" onClick={() => void cancelJob(cancellable)}>
      Cancel
    </button>
  ) : detail?.status === "needs-review" ? (
    <button className="primary" data-testid="accept" onClick={accept} disabled={accepting} aria-busy={accepting}>
      {accepting ? "Accepting…" : "Accept ▶"}
    </button>
  ) : next?.stage === detail?.stage && next?.command?.includes("--rerun") ? (
    <button className="primary" data-testid="rerun" onClick={() => void rerun()}>
      Re-run the Runner ▶
    </button>
  ) : detail && description?.implemented && detail.status !== "done" && detail.status !== "needs-input" ? (
    <button className="primary" data-testid="run" onClick={() => void run()}>
      Run ▶
    </button>
  ) : detail?.status === "done" && following ? (
    <button className="primary" data-testid="next" onClick={() => setStage(following)}>
      Next: {following} ▶
    </button>
  ) : null;

  return (
    <div className="app">
      <header>
        <button className="title" data-testid="home" onClick={goHome}>
          Kiripix
        </button>
        <span className="project">{data.status?.project}</span>
        <WorkStrip working={working} />
        <FilterBar filter={filter} onChange={setFilter} />
        {!connected && (
          <span className="offline" role="alert">
            Lost the connection to kiripix serve
          </span>
        )}
      </header>
      <AssetList status={data.status} selected={asset} filter={filter} onSelect={(id) => open(id, null)} />
      <main>
        {!asset || !show ? (
          <StatusBoard status={data.status} filter={filter} onOpen={open} />
        ) : isCharacterScreen && detail && description ? (
          <CharacterScreen
            key={`${asset}/${current}`}
            stage={current ?? ""}
            show={show}
            detail={detail}
            description={description}
            ownerAction={next && next.stage === detail.stage ? next.owner_action : null}
            refreshes={data.refreshes}
            disabled={busy}
            onPick={pick}
            onImport={(files, role) => void importFiles(files, role)}
            decide={decideCharacter}
          />
        ) : isSpriteFrames && detail && description ? (
          <SpriteFramesScreen
            key={`${asset}/${current}`}
            show={show}
            detail={detail}
            description={description}
            refreshes={data.refreshes}
            disabled={busy}
            onImport={(files, role) => void importFiles(files, role)}
            decide={decideCharacter}
          />
        ) : isFrames && detail ? (
          <FrameScreen
            key={`${asset}/${current}`}
            stage={current ?? ""}
            show={show}
            detail={detail}
            refreshes={data.refreshes}
            imageVersion={imageVersion}
            focus={focusFrame}
            pivotTool={isPivot ? { disabled: busy, decide: decidePivot } : undefined}
          />
        ) : isSource ? (
          <VariantGrid show={show} onPick={pick} onImport={(files) => void importFiles(files)} />
        ) : (
          <CanvasView
            canvas={canvas}
            after={after}
            before={before}
            frame={gameFrame ? show.resolution : null}
            fitKey={`${asset}/${current}`}
          />
        )}
      </main>
      <aside className="panel" aria-label="Stage panel">
        {show && detail && description ? (
          <>
            <h1 data-testid="stage-title">{detail.stage}</h1>
            <p>{description.description}</p>
            {detail.reason && <p className="reason">{detail.reason}</p>}
            {(nextLine || (next && next.stage === detail.stage && next.command)) && !stepsShown && (
              <div className="next-line" data-testid="next-hint">
                <span>{nextLine ?? <code>{next?.command}</code>}</span>
                {!cancellable && wantsReview && (
                  <button data-testid="next-accept" onClick={accept} disabled={accepting}>
                    Accept
                  </button>
                )}
                {!cancellable && !wantsReview && wantsRerun && (
                  <button data-testid="next-rerun" onClick={() => void rerun()}>
                    Re-run
                  </button>
                )}
              </div>
            )}
            {isPlace && (
              <PlacePanel
                key={asset}
                canvas={canvas}
                show={show}
                detail={detail}
                status={data.status}
                imageVersion={imageVersion}
                focusLayer={focusLayer}
                findings={data.checks}
                decide={decideMarker}
                decideAbove={decideAbove}
                disabled={busy}
              />
            )}
            {isFootprint && (
              <FootprintPanel
                key={asset}
                canvas={canvas}
                detail={detail}
                decide={decideFootprint}
                disabled={busy}
              />
            )}
            {isMasks && (
              <MasksPanel
                key={asset}
                canvas={canvas}
                asset={asset ?? ""}
                detail={detail}
                decisions={description.decisions}
                imageVersion={imageVersion}
                disabled={busy}
                rebuild={rebuild}
                onRebuild={setRebuild}
                decide={decideMask}
                importPng={importMask}
              />
            )}
            {isLayers && (
              <LayersPanel
                key={asset}
                canvas={canvas}
                asset={asset ?? ""}
                detail={detail}
                decisions={description.decisions}
                imageVersion={imageVersion}
                disabled={busy}
                rebuild={layersRebuild}
                onRebuild={setLayersRebuild}
                decide={decideMask}
                importPlate={importPlate}
              />
            )}
            {isReach && (
              <ReachPanel
                key={asset}
                canvas={canvas}
                show={show}
                detail={detail}
                imageVersion={imageVersion}
                onWalking={setGameFrame}
              />
            )}
            <fieldset disabled={busy}>
              {description.params.map((param) => (
                <ParamControl
                  key={`${detail.stage}.${param.name}.${refusals}`}
                  spec={param}
                  value={detail.params[param.name]}
                  onCommit={(value) => setParam(param.name, value)}
                />
              ))}
            </fieldset>
            {!isSource && !isCharacterScreen && !isSpriteFrames && !isFrames && image && (
              <label className="toggle">
                <input
                  type="checkbox"
                  data-testid="game-frame"
                  checked={gameFrame}
                  onChange={(event) => setGameFrame(event.target.checked)}
                />
                Game frame
              </label>
            )}
            {description.decisions.length > 0 && (
              <div className="decisions">
                <span data-testid="decision-count">{detail.decisions.length} Decision(s)</span>
                <button disabled={busy} onClick={() => step("undo")}>
                  Undo
                </button>
                <button disabled={busy} onClick={() => step("redo")}>
                  Redo
                </button>
              </div>
            )}
            <h2>Checks</h2>
            {stageChecks.length === 0 ? (
              <p className="pass" data-testid="checks-clean">
                ✓ Nothing to report
              </p>
            ) : (
              <FindingList findings={stageChecks} onJump={jump} testid="checks" />
            )}
            {noticeShown.length > 0 && (
              <>
                <h2>Last Command</h2>
                <FindingList findings={noticeShown} onJump={jump} testid="notice" />
              </>
            )}
            {progress && <p className="hint" data-testid="progress">{progress}</p>}
            <div className="primary-action">{primary}</div>
          </>
        ) : data.problems.length === 0 ? (
          <p className="hint">Choose an Asset to see its Stages.</p>
        ) : null}
        {problemsShown.length > 0 && (
          <>
            <h2>Can't read the Project</h2>
            <FindingList findings={problemsShown} onJump={jump} testid="problems" />
          </>
        )}
      </aside>
      <footer>
        {show && <StageBar stages={show.stages} selected={current} onSelect={setStage} />}
      </footer>
    </div>
  );
}
