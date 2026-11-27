import { useCallback, useEffect, useRef, useState } from "react";
import {
  assetFolder,
  call,
  callWithFile,
  callWithFiles,
  cancelJob,
  events,
  fileUrl,
  noteChange,
  pathsRelated,
  type DescribeData,
  type Envelope,
  type Finding,
  type NextData,
  type QueueData,
  type Scalar,
  type ShowData,
  type StageDescription,
  type StatusData,
  type StyleProbe,
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
import { NORMALS_STAGE, NormalsPanel } from "./normalsScreen";
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
import { SOUND_KIND, SOUND_STAGES, SoundScreen, type Provenance } from "./soundScreen";
import { NPC_KIND, NPC_STAGE, NpcCrowds, NpcScreen, npcFocusOf, type NpcFocus } from "./npcScreen";
import { DistrictOpen, DistrictView } from "./districtView";
import { WaitingRooms } from "./waitingRooms";
import { StylePanel } from "./styleScreen";
import { stopFinding, stopKey, QueueButton, QueueStrip } from "./queueMode";
import { WorkStrip, type Working } from "./workStrip";
import { assetOfPath, Rows } from "./rows";
import { EMOTION_DECISION, EmotionStrip, FACE_DECISION, FACE_STAGE, PORTRAIT_KIND, PortraitPanel } from "./portraitScreens";

const PICK = "pick"; // the Decision that makes a Stage's screen the Variant grid
const REFRESH_DELAY_MS = 100; // one refresh for a burst of "changed" events
const FOCUS_REFRESH_MS = 5000; // the window getting the focus reads everything again, at most this often

interface Scope {
  list: boolean; // the cheap list, and the status of `rows` and the queue
  queue: boolean; // the queue alone (a new match)
  rows: string[] | null; // the rows to ask again (null: every row)
  full: boolean; // a new token: the server reads everything again, as it is on disk
  asset: boolean; // `show`, `next`, `check` and `probe style` of the open Asset
  style: boolean; // the Project's style references may have changed
}


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
  queue: QueueData | null; // what waits on the Owner, narrowed by the session's match
  queueMatch: string; // the match `queue` was asked with
  queueFindings: Finding[];
  style: StyleProbe | null; // `probe style` of the Asset (or, with none open, of any: the references are the Project's)
  problems: Finding[]; // why the Project or the Asset can't be read
  refreshes: number; // the open Asset's calls have answered again: what its screen reads from files follows it
  coreFor: string | null; // the Asset whose `show` and `next` have both answered: only then is it known which Stage it opens on
  listRefreshes: number; // `status` has answered again: the views of the Project's rooms follow it
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

const MATCH_KEY = "kiripix.queue.match";
function readMatch(): string {
  try {
    return sessionStorage.getItem(MATCH_KEY) ?? "";
  } catch {
    return "";
  }
}
function saveMatch(value: string): void {
  try {
    sessionStorage.setItem(MATCH_KEY, value);
  } catch {
    // Without storage the match lasts until a reload.
  }
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
    queue: null,
    queueMatch: "",
    queueFindings: [],
    style: null,
    problems: [],
    refreshes: 0,
    listRefreshes: 0,
    coreFor: null,
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
  const [reading, setReading] = useState<{ label: string; since: number; left?: string[] } | null>({
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
  const [normalsRebuild, setNormalsRebuild] = useState(true); // a flatten replays with no Runner call
  const [layersRebuild, setLayersRebuild] = useState(false); // each rebuild is a Runner call, so it's the Owner's to ask for
  const [looksRebuild, setLooksRebuild] = useState(true); // a Look is built with no Runner, so a rebuild is cheap
  const [loopsRebuild, setLoopsRebuild] = useState(true); // so is a colour-cycle Loop
  const [focusLayer, setFocusLayer] = useState<{ layer: string; count: number } | null>(null); // a `layer.no_ysort` jump
  const [focusFrame, setFocusFrame] = useState<FrameFocus | null>(null); // a frame finding's jump
  const [, setRefocus] = useState(0); // one more render, to run the focus effect when a finding is on this Stage
  const [selectedState, setSelectedState] = useState<string | null>(null); // a Prop's state; null: the default state
  const [sideBySide, setSideBySide] = useState(false);
  const [styleFocus, setStyleFocus] = useState(0); // a `style.*` finding's jump
  const [npcFocus, setNpcFocus] = useState<NpcFocus | null>(null); // an `npc.*` finding's jump
  const [selectedEmotion, setSelectedEmotion] = useState<string | null>(null); // a portrait's emotion; null: the neutral
  const [faceRebuild, setFaceRebuild] = useState(true); // register again after each face edit, so the region shown is the Stage's
  // Queue mode (ticket 0329): `?queue=<glob>` opens it, as a district view's "Review this district" does. The match lasts the session.
  const [queueOn, setQueueOn] = useState(initialParam("queue") !== null);
  const [match, setMatch] = useState(initialParam("queue") ?? readMatch());
  // The district view (ticket 0330): the glob it shows, or null. `?district=<glob>` opens it.
  const [district, setDistrict] = useState<string | null>(initialParam("district"));
  const [cursorKey, setCursorKey] = useState<string | null>(null);
  const matchRef = useRef(match);
  matchRef.current = match;
  const lastIndex = useRef(0);
  const canvas = useRef<PixelCanvas>(null);
  const wearables = useWearables(data.status, data.listRefreshes);

  // One refresh at a time, and one more if something changed meanwhile: what shows is never older than a change. The calls of a refresh
  // are asked together and each answer shows as it lands (ticket 0369). A refresh asked for while one runs is merged into one more.
  const selection = useRef(asset);
  selection.current = asset;
  const dataRef = useRef(data);
  dataRef.current = data;
  const wearablesRef = useRef(wearables);
  wearablesRef.current = wearables;
  const rows = useRef<Rows | null>(null);
  if (!rows.current) {
    rows.current = new Rows(
      () => setData((before) => ({ ...before, status: rows.current!.snapshot(), problems: distinct([...rows.current!.problems, ...problemParts.current.show]) })),
      () => setConnected(false),
    );
  }
  const refreshing = useRef<Promise<void> | null>(null);
  const pending = useRef<Scope | null>(null);
  const styleFresh = useRef(false); // `probe style` has answered, and the references have not changed since
  const problemParts = useRef<{ show: Finding[] }>({ show: [] });

  // The folders whose change is the open Asset's: its own, its base's, its body's and its Wearables'.
  const openFolders = useCallback((): string[] => {
    const id = selection.current;
    if (!id) return [];
    const ids = new Set([id]);
    const shown = dataRef.current.show?.asset === id ? dataRef.current.show : null;
    if (shown?.base) ids.add(shown.base);
    for (const one of shown?.wearables ?? []) ids.add(one.asset);
    for (const one of Object.values(wearablesRef.current)) {
      if (one.id === id && one.body) ids.add(one.body);
      if (one.body === id) ids.add(one.id);
    }
    return [...ids].map(assetFolder);
  }, []);
  const scopeOf = useCallback(
    (paths: string[] | null): Scope => {
      if (paths === null) return { list: true, queue: true, rows: null, full: true, asset: true, style: true };
      const folders = openFolders();
      // Outside `assets/` is the Project's (`kiripix.toml`, the style references), which every Asset's calls may read.
      const project = paths.some((path) => !path.startsWith("assets/"));
      const mine = paths.some((path) => folders.some((folder) => pathsRelated(path, folder)));
      // Per row (ticket 0374): the Assets the paths name, and those that name them (a base's characters, a body's Wearables).
      const named = [...new Set(paths.flatMap((path) => assetOfPath(path) ?? []))];
      return { list: true, queue: true, rows: project ? null : rows.current!.related(named), full: false, asset: project || mine, style: project };
    },
    [openFolders],
  );
  // What an action may have changed: the open Asset and its dependants, or (a batch action, a new Asset) every row.
  const scopeAfterAction = useCallback(
    (everything: boolean): Scope => ({
      list: true,
      queue: true,
      rows: everything || !selection.current ? null : rows.current!.related([selection.current]),
      full: false,
      asset: true,
      style: true,
    }),
    [],
  );

  const readOnce = useCallback(async (scope: Scope) => {
    const chosen = selection.current;
    const alive = () => chosen === selection.current;
    const asked = matchRef.current;
    const left = new Set<string>();
    const reads: Promise<void>[] = [];
    const note = () => setReading((now) => (now ? { ...now, left: [...left] } : now));
    const read = (name: string, task: () => Promise<void>) => {
      left.add(name);
      note();
      reads.push(
        task()
          .then(() => setConnected(true))
          .catch(() => setConnected(false))
          .finally(() => {
            left.delete(name);
            note();
          }),
      );
    };
    const publish = (part: Partial<Selected> | ((before: Selected) => Partial<Selected>)) => {
      if (alive()) setData((before) => ({ ...before, ...(typeof part === "function" ? part(before) : part) }));
    };
    const problems = () => distinct([...rows.current!.problems, ...problemParts.current.show]);
    // The list is cheap and paints at once; each row's status, then the queue, fill in after it (ticket 0374).
    const store = rows.current!;
    let listed: Promise<void> = Promise.resolve();
    let firstRows: Promise<void> = Promise.resolve();
    if (scope.list) {
      if (scope.full) store.newToken();
      store.invalidate();
      listed = new Promise<void>((done) => {
        read("the list", async () => {
          try {
            await store.read();
          } finally {
            done();
          }
        });
      });
      firstRows = new Promise<void>((landed) => {
        read("the status", async () => {
          try {
            await listed;
            await store.start(scope.rows, landed);
            publish((before) => ({ problems: problems(), listRefreshes: before.listRefreshes + 1 }));
          } finally {
            landed();
          }
        });
      });
    }
    if (scope.list || scope.queue) {
      read("the queue", async () => {
        await listed;
        await firstRows;
        const waiting = await store.queue(scope.list ? scope.rows : null, asked, () => true);
        if (waiting) publish({ queue: waiting.data, queueMatch: asked, queueFindings: waiting.findings });
      });
    }
    if (chosen && scope.asset) {
      const core = [
        new Promise<void>((done) =>
          read("the Asset", async () => {
            try {
              const shown = await call<ShowData>("show", { asset: chosen });
              problemParts.current.show = shown.findings;
              publish({ show: shown.data, problems: problems() });
            } finally {
              done();
            }
          }),
        ),
        new Promise<void>((done) =>
          read("what is next", async () => {
            try {
              const answer = await call<NextData>("next", { asset: chosen });
              publish({ next: answer.data });
            } finally {
              done();
            }
          }),
        ),
      ];
      void Promise.all(core).then(() => publish((before) => ({ refreshes: before.refreshes + 1, coreFor: chosen })));
      read("the checks", async () => {
        const answer = await call<unknown>("check", { asset: chosen });
        publish({ checks: answer.findings });
      });
    }
    // The references are the Project's, so with no Asset open one ask is enough until they change.
    if (chosen ? scope.asset : scope.style || !styleFresh.current) {
      read("the style", async () => {
        if (!chosen) {
          await listed;
          await firstRows;
        }
        const styled = chosen ?? store.list[0]?.asset;
        if (!styled) return;
        const answer = await call<{ result: StyleProbe }>("probe", { name: "style", asset: styled });
        styleFresh.current = true;
        publish({ style: answer.data?.result ?? null });
      });
    }
    await Promise.all(reads);
  }, []);

  const ask = useCallback(
    (scope: Scope): Promise<void> => {
      if (scope.style) styleFresh.current = false;
      const before = pending.current;
      const union = (a: string[] | null, b: string[] | null) => (a === null || b === null ? null : [...new Set([...a, ...b])]);
      pending.current = before
        ? {
            list: before.list || scope.list,
            queue: before.queue || scope.queue,
            rows: before.list && scope.list ? union(before.rows, scope.rows) : before.list ? before.rows : scope.rows,
            full: before.full || scope.full,
            asset: before.asset || scope.asset,
            style: before.style || scope.style,
          }
        : scope;
      if (!refreshing.current) {
        refreshing.current = (async () => {
          while (pending.current) {
            const next = pending.current;
            pending.current = null;
            await readOnce(next);
          }
          refreshing.current = null;
          setReading(null);
        })();
      }
      return refreshing.current;
    },
    [readOnce],
  );
  // A refresh for the paths that changed (null: everything may have, and the server reads it all again).
  const refresh = useCallback((paths: string[] | null) => ask(scopeOf(paths)), [ask, scopeOf]);

  // Opening an Asset reads the Asset's calls; the list and the queue are asked only before they have ever answered.
  const refreshOpened = useCallback(() => {
    // The page's first read keeps what `serve` remembers (no new token): it is in step with every write Kiripix recorded.
    if (dataRef.current.status === null) return ask({ list: true, queue: true, rows: null, full: false, asset: true, style: true });
    return ask({ list: false, queue: false, rows: null, full: false, asset: true, style: false });
  }, [ask]);

  const lastRead = useRef(Date.now());
  useEffect(() => {
    let timer: number | undefined;
    let waiting: string[] | null = []; // what an agent changed since the last refresh (null: not known)
    let ours: string[] = []; // what `serve`'s own Commands changed since then
    let heard = false;
    let lost = false; // the stream failed before it connected: its first hello is a reconnect's
    const close = events({
      onChange: ({ paths, own, hello }) => {
        const first = hello && !heard && !lost; // the first connection: the page's own first refresh covers it
        if (hello) heard = true;
        if (first) return;
        // Only an image whose own file changed is fetched again.
        if (noteChange(paths)) setImageVersion((version) => version + 1);
        // A change `serve`'s own Commands made is read by the refresh of the action that made it: it starts none of its own, unless
        // an action is still running (a Decision's rebuild, say), whose half-way state is shown.
        const theirs = paths === null ? null : paths.filter((path) => !own.includes(path));
        if (paths !== null) ours = [...ours, ...paths.filter((path) => own.includes(path))];
        if (theirs !== null && theirs.length === 0 && ours.length === 0) return;
        waiting = theirs === null || waiting === null ? null : [...waiting, ...theirs];
        window.clearTimeout(timer);
        timer = window.setTimeout(() => {
          const mine = ours;
          const agents = waiting;
          ours = [];
          waiting = [];
          if (agents !== null && agents.length === 0) {
            if (mine.length > 0 && running.current > 0) void refresh(mine);
            return;
          }
          void refresh(agents === null ? null : running.current > 0 ? [...agents, ...mine] : agents);
        }, REFRESH_DELAY_MS);
      },
      onProgress: setProgress,
      onLost: () => {
        lost = true;
        setConnected(false);
      },
    });
    return () => {
      window.clearTimeout(timer);
      close();
    };
  }, [refresh, setProgress]);

  // A file changed outside Kiripix is never reported: the Reload button reads everything again, and the window getting the focus back
  // reads again what is on screen (the rows shown and the open Asset), which `serve` forgets first; every other row is kept, so a
  // Project of hundreds of Assets isn't worked out again on every switch of windows.
  const reload = useCallback(() => {
    lastRead.current = Date.now();
    noteChange(null);
    setImageVersion((version) => version + 1);
    setReading({ label: "Reading the Project", since: Date.now() });
    return refresh(null);
  }, [refresh]);
  useEffect(() => {
    const onFocus = () => {
      if (Date.now() - lastRead.current < FOCUS_REFRESH_MS) return;
      lastRead.current = Date.now();
      const store = rows.current!;
      const shown = [...new Set([...store.shown(), ...(selection.current ? [selection.current] : [])])];
      store.forgetOnce(shown);
      // An image's URL carries the number of the last change to its file (`fileUrl`): those Assets' files are taken as changed.
      noteChange(shown.map(assetFolder));
      setImageVersion((version) => version + 1);
      void ask({ list: true, queue: true, rows: shown, full: false, asset: true, style: false });
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [ask]);

  useEffect(() => {
    void refreshOpened();
  }, [asset, refreshOpened]);


  const show = data.show?.asset === asset ? data.show : null;
  // The board's rows are asked for only while it is on screen.
  const boardShown = (!asset || !show) && district === null;
  useEffect(() => {
    if (!boardShown) rows.current!.see("board", []);
  }, [boardShown]);
  const kind = show?.kind;
  const isProp = kind === "prop";
  const stateShown = isProp ? show?.states?.find((entry) => entry.state === selectedState) : undefined;
  const activeState = stateShown ? stateShown.state : null; // a state that was removed falls back to the default
  const isPortrait = kind === PORTRAIT_KIND;
  const emotionShown = isPortrait ? show?.emotions?.find((entry) => entry.emotion === selectedEmotion) : undefined;
  const activeEmotion = emotionShown ? emotionShown.emotion : null; // an emotion that was removed falls back to the neutral
  // The emotion or state the screen is on, whose Variants and Pick are its own (null: the Asset's); one helper for each use.
  const ownShown = emotionShown ?? stateShown;
  const ownTarget: { emotion?: string; state?: string } = activeEmotion ? { emotion: activeEmotion } : activeState ? { state: activeState } : {};
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
  const current = stage ?? next?.stage ?? (data.coreFor === asset ? show?.stages[0]?.stage : undefined) ?? null;
  useEffect(() => {
    if (stage === null && show && current) setStage(current);
  }, [stage, show, current]);

  useEffect(() => {
    const query = new URLSearchParams();
    if (asset) query.set("asset", asset);
    if (asset && current) query.set("stage", current);
    if (queueOn) query.set("queue", match);
    if (district !== null) query.set("district", district);
    const search = query.toString();
    history.replaceState(null, "", window.location.pathname + (search ? `?${search}` : ""));
  }, [asset, current, queueOn, match, district]);

  useActiveTime(asset, show ? current : null);

  const description = kind ? recipes[kind]?.find((entry) => entry.name === current) : undefined;
  const detail = show?.stages.find((entry) => entry.stage === current);
  // The looks Stage has a `pick` too, of a Look's edit: its own screen takes that.
  const isSource = current !== LOOKS_STAGE && current !== LOOPS_STAGE && (description?.decisions.some((decision) => decision.name === PICK) ?? false);
  const isPlace = description?.decisions.some((decision) => decision.name === PLACE_DECISION) ?? false;
  const isMasks =
    current === MASKS_STAGE && (description?.decisions.some((decision) => decision.name === "brush") ?? false);
  const isNormals =
    current === NORMALS_STAGE && show?.kind === "room" && (description?.decisions.some((decision) => decision.name === "flatten") ?? false);
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
  const isSound = show?.kind === SOUND_KIND && current !== null && SOUND_STAGES.includes(current);
  const isNpcChoose = show?.kind === NPC_KIND && current === NPC_STAGE && detail !== undefined;
  const isFace = isPortrait && current === FACE_STAGE && (description?.decisions.some((decision) => decision.name === FACE_DECISION) ?? false);
  const styleShown = data.style !== null && data.style.asset === asset && data.style.stage !== null && data.style.stage === current;
  const isFootprint = description?.decisions.some((decision) => decision.name === FOOTPRINT_DECISION) ?? false;

  // Each user action is one Command (a Mask edit may add a `run`, ADR 0006); its findings show until the next action. They
  // go one at a time, in the order they were made: a Run straight after a `set` must see that `set`, not find its lock held.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const running = useRef(0); // the actions whose Commands are being answered (not yet their refresh)
  const workIds = useRef(0);
  const perform = useCallback(
    <T,>(
      action: () => Promise<Envelope<T>>,
      label = "Working",
      kind: string | null = null,
      settled?: () => void,
      everything = false, // a batch action or a new Asset: every row is asked again, not the open Asset's and its dependants
    ): Promise<void> => {
      // Registered at once, so the strip and the marks show before the server has answered; it stays until its result landed.
      const id = ++workIds.current;
      setWorks((now) => [...now, { id, label, kind, since: null }]);
      const done = queue.current.then(async () => {
        setWorks((now) => now.map((work) => (work.id === id ? { ...work, since: Date.now() } : work)));
        try {
          running.current += 1;
          let result: Envelope<T>;
          try {
            result = await action();
          } finally {
            running.current -= 1;
          }
          setNotice(result.findings);
          setConnected(true);
          await ask(scopeAfterAction(everything));
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
    [ask, scopeAfterAction],
  );

  // A batch action of the district view: one Command with `--match`, through the same queue of actions as every other. A Run is
  // cancellable, as `run` is on a room.
  const batch = (command: string, input: object, label: string, cancellable: boolean) =>
    new Promise<Envelope<unknown> | null>((resolve) => {
      let result: Envelope<unknown> | null = null;
      void perform(async () => {
        const id = cancellable ? crypto.randomUUID() : undefined;
        if (id) setJob(id);
        try {
          result = await call<unknown>(command, input, id);
          return result;
        } finally {
          if (id) {
            setJob(null);
            setProgress(null);
          }
        }
      }, label, null, undefined, true).then(() => resolve(result));
    });

  // One file-carrying Command of the rooms waiting for a Source (ticket 0351), through the same queue of actions.
  const work = <T,>(label: string, action: () => Promise<Envelope<T>>) =>
    new Promise<Envelope<T> | null>((resolve) => {
      let result: Envelope<T> | null = null;
      void perform(async () => {
        result = await action();
        return result;
      }, label, null, undefined, true).then(() => resolve(result));
    });

  // `style-add` and `style-remove` are the Owner's: `call` sends the session token.
  const setReference = (add: boolean) => void perform(() => call(add ? "style-add" : "style-remove", { asset }), add ? "Making a style reference" : "Removing a style reference", null, undefined, true);

  // A Run holds the Asset's lock, and what is done meanwhile would be refused or make its output stale at once.
  const busy = job !== null;
  const setParam = (name: string, value: Scalar) =>
    void perform(async () => {
      const result = await call("set", { asset, stage: current, assignments: [`${name}=${value}`] });
      if (!result.ok) setRefusals((count) => count + 1); // The control goes back to the value that stands.
      return result;
    }, `Setting ${name}`);
  // A change of an NPC's choice is one `set` of one `choose` parameter, then `choose` again (no Runner) so the figure shows it.
  const setChoice = (name: string, value: string) =>
    void perform(async () => rebuilt(await call("set", { asset, stage: current, assignments: [`${name}=${value}`] }), false, true), `Setting ${name}`);
  // "re-roll" on the board: `new --reroll`, then the NPC's `choose` again, which is how a crowd is built.
  const rerollNpc = (id: string) =>
    work("Re-rolling " + id, async () => {
      const made = await call("new", { kind: NPC_KIND, name: id, reroll: true });
      if (!made.ok) return made;
      const ran = await call("run", { asset: id, stage: NPC_STAGE });
      return { ...ran, findings: [...made.findings, ...ran.findings] };
    });
  // The Sound screen's actions: one Command each, through the same queue; a recording is imported with its Provenance and picked.
  const soundAct = (label: string, command: string, input: object) => work(label, () => call(command, input));
  const soundImport = (file: File, provenance: Provenance) =>
    void work("Importing " + file.name, async () => {
      const given = Object.fromEntries(Object.entries(provenance).filter(([, text]) => text.trim() !== ""));
      const stored = await callWithFile<{ variant: string }>("import", { asset, ...given }, "file", file);
      if (!stored.ok || !stored.data) return stored;
      const picked = await call("pick", { asset, variant: stored.data.variant });
      return { ...picked, findings: [...stored.findings, ...picked.findings] };
    });
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
  const rebuildOn = [
    [isMasks, rebuild],
    [isLooks, looksRebuild],
    [isLoops, loopsRebuild],
    [isFace, faceRebuild],
    [isLayers, layersRebuild],
    [isNormals, normalsRebuild],
  ].find(([screen]) => screen)?.[1] ?? false;
  const rebuilt = useCallback(
    async <T,>(result: Envelope<T>, rerun = false, force = false): Promise<Envelope<unknown>> => {
      // `force`: a removed Layer is taken out by a plain `run layers`, with no rerun and no accept (ticket 0091).
      if (!(force || rebuildOn) || !result.ok) return result;
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
    [asset, current, rebuildOn],
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
        face: "Drawing the face region",
        flatten: "Flattening",
      };
      const label =
        name === "click" && isLayers
          ? data.positive === false
            ? `Taking from ${into}`
            : `Lifting into ${into}`
          : `${verbs[name] ?? "Deciding on"} ${into}`.trim();
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
  // An Override painted on the normals' image: one `override`, then the Stage again so the picture shows it (ticket 0343).
  const overrideNormals = useCallback(
    (file: File, settled?: () => void) =>
      void perform(async () => rebuilt(await callWithFile("override", { asset, stage: current }, "png", file)), "Painting the normals", null, settled),
    [asset, current, perform, rebuilt],
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
          () => call("pick", { asset, variant, ...ownTarget }),
          activeEmotion ? `Picking an image of ${activeEmotion}` : activeState ? `Picking a Variant of ${activeState}` : "Picking a Variant",
        );
    },
    [activeEmotion, activeState, asset, busy, perform, ownTarget.emotion, ownTarget.state],
  );
  const importFiles = async (files: File[], role: ImportRole = "variant", extra: object = {}) => {
    for (const file of files) {
      const input = role === "variant" && ownShown ? { asset, ...ownTarget } : { asset, role, ...extra };
      await perform(() => callWithFile("import", input, "file", file), `Importing ${file.name}`);
    }
  };
  // An emotion is declared on `source`, whatever Stage is open: one `decide`.
  const declareEmotion = useCallback(
    (id: string) => {
      const decision = JSON.stringify({ decision: EMOTION_DECISION, data: { id } });
      void perform(async () => {
        const result = await call("decide", { asset, stage: "source", decision });
        if (result.ok) setSelectedEmotion(id);
        return result;
      }, `Declaring the emotion ${id}`);
    },
    [asset, perform],
  );
  // An image dropped on an emotion in the strip is stored as its Variant and picked at once, as an edit of a Look is.
  const importEmotion = useCallback(
    (file: File, emotion: string) =>
      void perform(async () => {
        const stored = await callWithFile<{ variant: string }>("import", { asset, emotion }, "file", file);
        if (!stored.ok || !stored.data) return stored;
        const picked = await call("pick", { asset, emotion, variant: stored.data.variant });
        return { ...picked, findings: [...stored.findings, ...picked.findings] };
      }, `Importing an image of ${emotion}`),
    [asset, perform],
  );
  // `new` for a character: one Command, and the new Asset opens when it was made. A parameter file goes with it.
  const createCharacter = (name: string, base: string, parameters: File | null) =>
    void perform(async () => {
      const input = { kind: CHARACTER_KIND, name, ...(base ? { base } : {}) };
      const result = parameters
        ? await callWithFile<{ asset: string }>("new", input, "from_parameters", parameters)
        : await call<{ asset: string }>("new", input);
      if (result.ok && result.data) open(result.data.asset, null);
      return result;
    }, `Creating ${name}`, null, undefined, true);
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
            return rebuilt(result, false, isLayers || isPivot || (isLooks && looksRebuild) || (isLoops && loopsRebuild) || (isFace && faceRebuild));
          },
          command === "undo" ? "Undoing" : "Redoing",
        );
    },
    [asset, busy, current, faceRebuild, isFace, isLayers, isLooks, isLoops, isPivot, looksRebuild, loopsRebuild, perform, rebuilt],
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

  const variants = ownShown ? ownShown.variants : show?.variants;
  const gridShow = show && ownShown ? { ...show, variants: ownShown.variants, picked: ownShown.picked } : show;
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
    setQueueOn(false);
    setDistrict(null);
    setReading({ label: "Opening the room list", since: Date.now() });
    if (selection.current === null) void ask(scopeAfterAction(true));
    setAsset(null);
  }

  function open(assetId: string, stageName: string | null) {
    setReading({ label: `Opening ${assetId}`, since: Date.now() });
    if (assetId === selection.current) void ask(scopeAfterAction(false)); // the effect runs only when the Asset changes
    setAsset(assetId);
    setStage(stageName);
    setNotice([]);
    setFocusLayer(null);
    setFocusFrame(null);
    setSelectedState(null);
    setSelectedEmotion(null);
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
    if (finding.code.startsWith("style.")) setStyleFocus((count) => count + 1);
    const npc = npcFocusOf(finding);
    if (npc) setNpcFocus((before) => ({ ...npc, count: (before?.count ?? 0) + 1 }));
    if (layer) setFocusLayer((before) => ({ layer, count: (before?.count ?? 0) + 1 }));
    if (where && where !== current) setStage(where);
    else setRefocus((count) => count + 1);
  }

  // Queue mode: each stop opens its Asset on its Stage, as clicking the Stage does; a finding jumps to its place.
  const stops = data.queue?.stops ?? [];
  const goTo = (index: number, list: QueueData["stops"] = stops) => {
    const stop = list[index];
    if (!stop) return;
    lastIndex.current = index;
    setCursorKey(stopKey(stop));
    open(stop.asset, stop.stage);
    if (stop.type === "finding" && stop.position) jump(stopFinding(stop));
  };
  const leaveQueue = () => setQueueOn(false);
  const openQueue = (glob?: string) => {
    if (glob !== undefined && glob !== match) changeMatch(glob);
    lastIndex.current = 0;
    setCursorKey(null);
    setQueueOn(true);
  };
  const changeMatch = (value: string) => {
    saveMatch(value);
    matchRef.current = value;
    setMatch(value);
    setCursorKey(null);
    lastIndex.current = 0;
    void ask({ list: false, queue: true, rows: null, full: false, asset: false, style: false });
  };
  const references = (data.status?.assets ?? []).filter((row) => row.reference).map((row) => row.asset);
  const queueIndex = stops.findIndex((stop) => stopKey(stop) === cursorKey);
  // Once the queue for the match in force has landed: the current stop stays while it waits, else the one now at its place.
  useEffect(() => {
    if (!queueOn || data.queueMatch !== match) return;
    if (stops.length === 0) {
      setCursorKey(null);
      return;
    }
    const found = cursorKey === null ? -1 : stops.findIndex((stop) => stopKey(stop) === cursorKey);
    if (found >= 0) lastIndex.current = found;
    else goTo(Math.min(lastIndex.current, stops.length - 1));
  }, [queueOn, data.queue, data.queueMatch, match, cursorKey]);

  // `A` accepts a review, `→` or `N` the next stop, `←` or `P` the previous. In the capture phase, so that in queue mode they win
  // over a Stage's own use of the same key (panning by arrow, a Mask named `a`); `Esc` leaves unless a tool took it first.
  const queueKeys = useRef({ goTo, accept, leaveQueue, stops, index: queueIndex, review: false });
  queueKeys.current = {
    goTo,
    accept,
    leaveQueue,
    stops,
    index: queueIndex,
    review: queueIndex >= 0 && stops[queueIndex].type === "review" && stops[queueIndex].stage === current && detail?.status === "needs-review" && job === null && rebuilding === null,
  };
  useEffect(() => {
    if (!queueOn) return;
    const onCapture = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
      const now = queueKeys.current;
      const key = event.key.toLowerCase();
      const step = key === "arrowright" || key === "n" ? 1 : key === "arrowleft" || key === "p" ? -1 : 0;
      if (step !== 0) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const at = now.index + step;
        if (at >= 0 && at < now.stops.length) now.goTo(at);
      } else if (key === "a" && now.review) {
        event.preventDefault();
        event.stopImmediatePropagation();
        now.accept();
      }
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented && !isTyping(event.target)) queueKeys.current.leaveQueue();
    };
    window.addEventListener("keydown", onCapture, true);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("keydown", onCapture, true);
      window.removeEventListener("keydown", onEscape);
    };
  }, [queueOn]);

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
      ? { label: reading.left?.length ? `${reading.label}: reading ${reading.left.join(", ")}` : reading.label, since: reading.since, waiting: 0, progress: null, fraction: null }
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
        <QueueButton
          testid="queue-open"
          count={data.queue ? data.queue.counts.total : null}
          active={queueOn}
          onClick={() => (queueOn ? leaveQueue() : openQueue())}
        />
        {district !== null && asset && (
          <button data-testid="district-back" onClick={() => setAsset(null)} title="Back to the district">
            District {district}
          </button>
        )}
        <button data-testid="reload" onClick={() => void reload()} title="Read the Project again, as it is on disk">
          Reload
        </button>
        <FilterBar filter={filter} onChange={setFilter} />
        {!connected && (
          <span className="offline" role="alert">
            Lost the connection to kiripix serve
          </span>
        )}
      </header>
      {queueOn && (
        <QueueStrip
          queue={data.queueMatch === match ? data.queue : null}
          findings={data.queueMatch === match ? data.queueFindings : []}
          index={queueIndex}
          match={match}
          onMatch={changeMatch}
          onGo={goTo}
          onLeave={leaveQueue}
        />
      )}
      <AssetList
        status={data.status}
        selected={asset}
        filter={filter}
        references={references}
        onSelect={(id) => open(id, null)}
        onSee={(ids) => rows.current!.see("list", ids)}
      />
      <main>
        {(!asset || !show) && district !== null ? (
          <DistrictView
            glob={district}
            refreshes={data.listRefreshes}
            imageVersion={imageVersion}
            job={job}
            progress={progress}
            onOpen={open}
            onReview={openQueue}
            onClose={() => setDistrict(null)}
            batch={batch}
            extra={() => <WaitingRooms glob={district!} refreshes={data.listRefreshes} imageVersion={imageVersion} work={work} onOpen={open} />}
          />
        ) : !asset || !show ? (
          <StatusBoard
            status={data.status}
            filter={filter}
            references={references}
            onOpen={open}
            onSee={(ids) => rows.current!.see("board", ids)}
            queue={
              <QueueButton testid="board-queue" count={data.queue ? data.queue.counts.total : null} active={queueOn} onClick={() => openQueue()} />
            }
            district={<DistrictOpen assets={data.status?.assets ?? []} onOpen={setDistrict} />}
            onCreateCharacter={createCharacter}
            worn={Object.fromEntries(Object.values(wearables).map((one) => [one.id, { body: one.body, cost: costText(one) }]))}
            crowds={
              <NpcCrowds status={data.status} refreshes={data.listRefreshes} imageVersion={imageVersion} disabled={busy} onOpen={open} onReroll={rerollNpc} />
            }
          />
        ) : isSound && show ? (
          <SoundScreen
            key={`${asset}/${current}`}
            show={show}
            stage={current ?? ""}
            stages={kind ? recipes[kind] : undefined}
            findings={stageChecks}
            refreshes={data.refreshes}
            imageVersion={imageVersion}
            disabled={busy}
            act={soundAct}
            onPick={pick}
            onImport={soundImport}
          />
        ) : isNpcChoose && detail ? (
          <NpcScreen
            key={asset}
            show={show}
            detail={detail}
            wearables={Object.values(wearables).filter((one) => one.body === show.base)}
            findings={stageChecks}
            focus={npcFocus}
            refreshes={data.refreshes}
            imageVersion={imageVersion}
            disabled={busy}
            onSet={setChoice}
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
            onImport={(files, role, extra) => void importFiles(files, role, extra)}
            onRemoveThing={(thing) => void perform(() => call("thing-remove", { asset, thing }), `Removing the thing ${thing}`)}
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
            {styleShown && data.style && (
              <StylePanel
                key={asset}
                probe={data.style}
                show={show}
                findings={stageChecks}
                focus={styleFocus}
                refreshes={data.refreshes}
                imageVersion={imageVersion}
                disabled={busy}
                setReference={setReference}
              />
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
            {isPortrait && (
              <EmotionStrip
                show={show}
                emotion={activeEmotion}
                findings={data.checks}
                imageVersion={imageVersion}
                disabled={busy}
                onSelect={setSelectedEmotion}
                declare={declareEmotion}
                importAndPick={importEmotion}
              />
            )}
            {isPortrait && !isSource && (
              <PortraitPanel
                key={`${asset}/${current}`}
                canvas={canvas}
                show={show}
                stage={current ?? ""}
                detail={detail}
                emotion={activeEmotion}
                onSelect={setSelectedEmotion}
                findings={data.checks}
                imageVersion={imageVersion}
                disabled={busy}
                rebuild={faceRebuild}
                onRebuild={setFaceRebuild}
                decide={decideMask}
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
                view={String(show?.params.view ?? "top")}
                place={show?.stages.find((entry) => entry.stage === "place")}
                refreshes={data.refreshes}
              />
            )}
            {isNormals && (
              <NormalsPanel
                key={asset}
                canvas={canvas}
                asset={asset ?? ""}
                show={show}
                detail={detail}
                decisions={description.decisions}
                imageVersion={imageVersion}
                disabled={busy}
                rebuild={normalsRebuild}
                onRebuild={setNormalsRebuild}
                findings={stageChecks}
                decide={decideMask}
                overridePng={overrideNormals}
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
              {description.params.filter((param) => !isNpcChoose || (param.name !== "wearables" && param.name !== "colours")).map((param) => (
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
