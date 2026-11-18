import { useCallback, useEffect, useRef, useState } from "react";
import {
  call,
  callWithFile,
  callWithFiles,
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
import { useActiveTime } from "./activeTime";
import { MASKS_STAGE, MasksPanel } from "./maskScreen";
import { LOOKS_DECISION, LOOKS_STAGE, LooksPanel, roomImageOf } from "./lookScreen";
import { LOOPS_DECISION, LOOPS_STAGE, LoopsPanel } from "./loopScreen";
import { ambiguousCells } from "./markerTool";
import { ABOVE_DECISION, LINK_DECISION, PLACE_DECISION, PlacePanel, REACH_STAGE, ReachPanel } from "./roomScreens";
import {
  FOOTPRINT_DECISION,
  FootprintPanel,
  ICON_FIT_STAGE,
  ICON_KIND,
  IconSquarePanel,
  SideBySide,
  STATE_DECISION,
  STATE_OFFSET_DECISION,
  StateOffsetPanel,
  StateStrip,
  stateImage,
} from "./propScreens";
import { LAYERS_DECISION, LAYERS_STAGE, LayersPanel } from "./layerScreen";
import { layerIdOf } from "./sortView";
import { CHARACTER_KIND, CHARACTER_SCREENS, CharacterScreen, type ImportRole } from "./characterScreens";
import { SPRITE_FRAMES_STAGE, SPRITE_KIND, SpriteFramesScreen } from "./spriteScreens";
import { FRAME_STAGES, FrameScreen, frameOf, type FrameFocus } from "./frameScreen";
import { costText, StackPreview, useWearables } from "./wearableScreens";
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
  const [looksRebuild, setLooksRebuild] = useState(true); // a Look is built with no Runner, so a rebuild is cheap
  const [loopsRebuild, setLoopsRebuild] = useState(true); // so is a colour-cycle Loop
  const [focusLayer, setFocusLayer] = useState<{ layer: string; count: number } | null>(null); // a `layer.no_ysort` jump
  const [focusFrame, setFocusFrame] = useState<FrameFocus | null>(null); // a frame finding's jump
  const [, setRefocus] = useState(0); // one more render, to run the focus effect when a finding is on this Stage
  const [selectedState, setSelectedState] = useState<string | null>(null); // a Prop's state; null: the default state
  const [sideBySide, setSideBySide] = useState(false);
  const canvas = useRef<PixelCanvas>(null);
  const wearables = useWearables(data.status, data.refreshes);

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
  const isProp = kind === "prop";
  const stateShown = isProp ? show?.states?.find((entry) => entry.state === selectedState) : undefined;
  const activeState = stateShown ? stateShown.state : null; // a state that was removed falls back to the default
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

  useActiveTime(asset, show ? current : null);

  const description = kind ? recipes[kind]?.find((entry) => entry.name === current) : undefined;
  const detail = show?.stages.find((entry) => entry.stage === current);
  // The looks Stage has a `pick` too, of a Look's edit: its own screen takes that.
  const isSource = current !== LOOKS_STAGE && current !== LOOPS_STAGE && (description?.decisions.some((decision) => decision.name === PICK) ?? false);
  const isPlace = description?.decisions.some((decision) => decision.name === PLACE_DECISION) ?? false;
  const isMasks =
    current === MASKS_STAGE && (description?.decisions.some((decision) => decision.name === "brush") ?? false);
  const isLayers =
    current === LAYERS_STAGE && (description?.decisions.some((decision) => decision.name === LAYERS_DECISION) ?? false);
  const isLooks =
    current === LOOKS_STAGE && show?.kind === "room" && (description?.decisions.some((decision) => decision.name === LOOKS_DECISION) ?? false);
  const isLoops =
    current === LOOPS_STAGE && show?.kind === "room" && (description?.decisions.some((decision) => decision.name === LOOPS_DECISION) ?? false);
  const isReach = current === REACH_STAGE && show?.kind === "room";
  const isCharacterScreen =
    show?.kind === CHARACTER_KIND && current !== null && CHARACTER_SCREENS.includes(current) && description !== undefined;
  const wearablesOfBody = Object.values(wearables).filter((one) => one.body === asset && one.id !== asset);
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
  const decideLink = useCallback(
    (link: Record<string, unknown>) => {
      const decision = JSON.stringify({ decision: LINK_DECISION, data: link });
      void perform(() => call("decide", { asset, stage: current, decision }), "Placing a link");
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
      const decision = JSON.stringify({ decision: FOOTPRINT_DECISION, data: { ...footprint, ...(activeState ? { state: activeState } : {}) } });
      void perform(() => call("decide", { asset, stage: current, decision }), activeState ? `Setting the footprint of ${activeState}` : "Setting the footprint");
    },
    [activeState, asset, current, perform],
  );
  // A state is declared on `source`, whatever Stage is open: one `decide`.
  const declareState = useCallback(
    (id: string, width: number, height: number) => {
      const decision = JSON.stringify({ decision: STATE_DECISION, data: { id, width, height } });
      void perform(async () => {
        const result = await call("decide", { asset, stage: "source", decision });
        if (result.ok) setSelectedState(id);
        return result;
      }, `Declaring the state ${id}`);
    },
    [asset, perform],
  );
  const decideStateOffset = useCallback(
    (offsetX: number, offsetY: number) => {
      const decision = JSON.stringify({ decision: STATE_OFFSET_DECISION, data: { state: activeState, offset_x: offsetX, offset_y: offsetY } });
      void perform(() => call("decide", { asset, stage: current, decision }), `Setting the crop of ${activeState}`);
    },
    [activeState, asset, current, perform],
  );
  // A Mask edit shows once the Stage has run again, so with "rebuild" on the same action runs it, as a refresh would.
  // Only a `click` asks for a Runner's result, hence `rerun` for it alone: no other edit may re-run a pinned call (ADR 0002).
  // It can be cancelled, but it doesn't make the screen busy: the queue keeps quick strokes in order, and none is dropped.
  const rebuilt = useCallback(
    async <T,>(result: Envelope<T>, rerun = false, force = false): Promise<Envelope<unknown>> => {
      // `force`: a removed Layer is taken out by a plain `run layers`, with no rerun and no accept (ticket 0091).
      if (!(force || (isMasks ? rebuild : isLooks ? looksRebuild : isLoops ? loopsRebuild : isLayers && layersRebuild)) || !result.ok) return result;
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
    [asset, current, isMasks, isLayers, isLooks, isLoops, rebuild, layersRebuild, looksRebuild, loopsRebuild],
  );
  const decideMask = useCallback(
    (name: string, data: Record<string, unknown>, settled?: () => void) => {
      const decision = JSON.stringify({ decision: name, data });
      const into = String(data.layer ?? data.mask ?? data.look ?? data.loop ?? "");
      const verbs: Record<string, string> = {
        trim: "Trimming",
        brush: data.erase ? "Erasing" : "Painting",
        flood: "Flooding",
        click: "Clicking into",
        border: "Bordering",
        remove: "Removing",
        rename: "Renaming",
        polygon: "Filling",
        solid: "Painting the solid of",
        difference: "Measuring the difference of",
        look: "Naming",
        loop: "Declaring",
        cycle: "Setting the cycle of",
        timing: "Setting the timing of",
        frames: "Setting the frames of",
        hold: "Holding a part of",
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
  // An edit dropped on the looks screen is stored as a Variant of its Look and picked at once: the Owner dropped it to use it.
  const importEdit = useCallback(
    (file: File, look: string) =>
      void perform(async () => {
        const stored = await callWithFile<{ variant: string }>("import", { asset, look }, "file", file);
        if (!stored.ok || !stored.data) return stored;
        const picked = await call("pick", { asset, look, variant: stored.data.variant });
        return rebuilt({ ...picked, findings: [...stored.findings, ...picked.findings] });
      }, `Importing an edit of ${look}`),
    [asset, perform, rebuilt],
  );
  // An older edit of a Look, picked from the list (ticket 0209): one `pick --look`.
  const pickEdit = useCallback(
    (look: string, variant: string) => {
      if (!busy) void perform(async () => rebuilt(await call("pick", { asset, look, variant })), `Picking an edit of ${look}`);
    },
    [asset, busy, perform, rebuilt],
  );
  // A frame Loop's kit (ticket 0196): written to a folder on the server's machine; the painted frames come back from there.
  // `import --loop` takes a JSON list of paths over REST (multipart takes one file), so the folder is named, not uploaded.
  const writeKit = useCallback(
    (loop: string, folder: string, frames: number, force: boolean, written: (folder: string | null) => void) =>
      void perform(async () => {
        const result = await call<{ folder: string }>("loop kit", { asset, loop, folder, frames, force });
        written(result.ok && result.data ? result.data.folder : null);
        return result;
      }, `Writing the kit of ${loop}`),
    [asset, perform],
  );
  const importFrames = useCallback(
    (loop: string, paths: string[]) =>
      void perform(async () => {
        const [file, ...frames] = paths;
        return rebuilt(await call("import", { asset, loop, file, frames }));
      }, `Importing the frames of ${loop}`),
    [asset, perform, rebuilt],
  );
  // Frames dropped or picked (ticket 0210): one multipart `import --loop`, the first PNG as `file`, the others as `frames` parts, and
  // the kit's `kit.json` as `kit`. The Command sorts them by the names they were sent with.
  const importFrameFiles = useCallback(
    (loop: string, frames: File[], kit: File | null) =>
      void perform(async () => {
        const [first, ...rest] = frames;
        const parts = [{ field: "file", file: first }, ...rest.map((file) => ({ field: "frames", file })), ...(kit ? [{ field: "kit", file: kit }] : [])];
        return rebuilt(await callWithFiles("import", { asset, loop }, parts));
      }, `Importing the frames of ${loop}`),
    [asset, perform, rebuilt],
  );
  // An edit frame of a Loop (ticket 0221): stored for its frame, then picked at once, as an edit of a Look is. `import.edit_of_an_edit`
  // comes back from the import, and the screen shows it on that frame.
  const importLoopEdit = useCallback(
    (loop: string, frame: number, file: File, noted: (findings: Finding[]) => void) =>
      void perform(async () => {
        const stored = await callWithFile<{ variant: string }>("import", { asset, loop, frame }, "file", file);
        noted(stored.findings);
        if (!stored.ok || !stored.data) return stored;
        const picked = await call("pick", { asset, loop, frame, variant: stored.data.variant });
        return rebuilt({ ...picked, findings: [...stored.findings, ...picked.findings] });
      }, `Importing an edit for frame ${frame} of ${loop}`),
    [asset, perform, rebuilt],
  );
  const pick = useCallback(
    (variant: string) => {
      if (!busy)
        void perform(
          () => call("pick", { asset, variant, ...(activeState ? { state: activeState } : {}) }),
          activeState ? `Picking a Variant of ${activeState}` : "Picking a Variant",
        );
    },
    [activeState, asset, busy, perform],
  );
  const importFiles = async (files: File[], role: ImportRole = "variant") => {
    for (const file of files) {
      const input = activeState && role === "variant" ? { asset, state: activeState } : { asset, role };
      await perform(() => callWithFile("import", input, "file", file), `Importing ${file.name}`);
    }
  };
  // `new` for a character: one Command, and the new Asset opens when it was made. A parameter file goes with it.
  const createCharacter = (name: string, base: string, parameters: File | null) =>
    void perform(async () => {
      const input = { kind: CHARACTER_KIND, name, ...(base ? { base } : {}) };
      const result = parameters
        ? await callWithFile<{ asset: string }>("new", input, "from_parameters", parameters)
        : await call<{ asset: string }>("new", input);
      if (result.ok && result.data) open(result.data.asset, null);
      return result;
    }, `Creating ${name}`);
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
            return rebuilt(result, false, isLayers || isPivot || (isLooks && looksRebuild) || (isLoops && loopsRebuild));
          },
          command === "undo" ? "Undoing" : "Redoing",
        );
    },
    [asset, busy, current, isLayers, isLooks, isLoops, isPivot, looksRebuild, loopsRebuild, perform, rebuilt],
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

  const variants = stateShown ? stateShown.variants : show?.variants;
  const gridShow = show && stateShown ? { ...show, variants: stateShown.variants, picked: stateShown.picked } : show;
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
    setSelectedState(null);
    setSideBySide(false);
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
  // A Loop that flashes too fast is an error that holds the Stage back: its timing is changed first.
  const blocked = isLoops && stageChecks.some((finding) => finding.severity === "error");
  const asking = pressing([...stageChecks, ...noticeShown, ...problemsShown]);
  const nextLine =
    next && next.stage === detail?.stage && next.owner_action
      ? next.owner_action
      : wantsReview
        ? "Look at the result, then accept it to go on."
        : asking?.owner_action;
  // Reach has no image of its own, and the Body walks on the mapped room that `place` is made on.
  const reachImage = isReach ? show?.stages.find((entry) => entry.stage === "place")?.input_image : null;
  const image =
    ((isLooks || isLoops) && show ? roomImageOf(show) : null) ??
    stateImage(show, detail?.stage, activeState, "image") ??
    stateImage(show, detail?.stage, activeState, "input_image") ??
    reachImage ??
    null;
  const after = image ? fileUrl(image, imageVersion) : null;
  const beforeImage = stateImage(show, detail?.stage, activeState, "input_image");
  const before = stateImage(show, detail?.stage, activeState, "image") && beforeImage ? fileUrl(beforeImage, imageVersion) : null;

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
  ) : blocked ? (
    <button className="primary" data-testid="accept" disabled title="Fix the errors of the Loops first">
      Accept ▶
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
          <StatusBoard
            status={data.status}
            filter={filter}
            onOpen={open}
            onCreateCharacter={createCharacter}
            worn={Object.fromEntries(Object.values(wearables).map((one) => [one.id, { body: one.body, cost: costText(one) }]))}
          />
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
            onOpen={(id) => open(id, null)}
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
          <div className="frames-with-stack">
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
            {current === "sheet" && kind === CHARACTER_KIND && wearablesOfBody.length > 0 && (
              <StackPreview
                key={asset}
                show={show}
                wearables={wearablesOfBody}
                findings={data.checks}
                refreshes={data.refreshes}
                imageVersion={imageVersion}
              />
            )}
          </div>
        ) : isProp && sideBySide ? (
          <SideBySide show={show} imageVersion={imageVersion} />
        ) : isSource ? (
          <VariantGrid show={gridShow ?? show} onPick={pick} onImport={(files) => void importFiles(files)} />
        ) : (
          <CanvasView
            canvas={canvas}
            after={after}
            before={before}
            frame={gameFrame ? show.resolution : null}
            fitKey={`${asset}/${current}/${activeState ?? ""}`}
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
                  <button data-testid="next-accept" onClick={accept} disabled={accepting || blocked}>
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
            {isProp && (
              <StateStrip
                show={show}
                state={activeState}
                findings={data.checks}
                imageVersion={imageVersion}
                disabled={busy}
                sideBySide={sideBySide}
                onSelect={setSelectedState}
                onSideBySide={setSideBySide}
                declare={declareState}
                importFiles={(files) => void importFiles(files)}
              />
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
                decideLink={decideLink}
                decideAbove={decideAbove}
                disabled={busy}
              />
            )}
            {kind === ICON_KIND && current === ICON_FIT_STAGE && (
              <IconSquarePanel key={asset} canvas={canvas} show={show} detail={detail} refreshes={data.refreshes} />
            )}
            {isFootprint && (
              <FootprintPanel
                key={`${asset}/${activeState ?? ""}`}
                canvas={canvas}
                detail={detail}
                state={activeState}
                decide={decideFootprint}
                disabled={busy}
              />
            )}
            {activeState && description.decisions.some((decision) => decision.name === STATE_OFFSET_DECISION) && (
              <StateOffsetPanel detail={detail} state={activeState} disabled={busy} decide={decideStateOffset} />
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
            {isLooks && (
              <LooksPanel
                key={asset}
                canvas={canvas}
                asset={asset ?? ""}
                show={show}
                detail={detail}
                decisions={description.decisions}
                imageVersion={imageVersion}
                refreshes={data.refreshes}
                disabled={busy}
                rebuild={looksRebuild}
                onRebuild={setLooksRebuild}
                decide={decideMask}
                importEdit={importEdit}
                pickEdit={pickEdit}
              />
            )}
            {isLoops && (
              <LoopsPanel
                key={asset}
                canvas={canvas}
                show={show}
                detail={detail}
                decisions={description.decisions}
                findings={stageChecks}
                imageVersion={imageVersion}
                refreshes={data.refreshes}
                disabled={busy}
                rebuild={loopsRebuild}
                onRebuild={setLoopsRebuild}
                roomImage={roomImageOf(show)}
                decide={decideMask}
                writeKit={writeKit}
                importFrames={importFrames}
                importFrameFiles={importFrameFiles}
                notice={noticeShown}
                importEdit={importLoopEdit}
                onStage={setStage}
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
                  origin={detail.param_sources?.[param.name]}
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
