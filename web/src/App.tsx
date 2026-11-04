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
  StageBar,
  StatusBoard,
  VariantGrid,
  type Filter,
} from "./components";
import type { PixelCanvas } from "./pixelCanvas";
import { PLACE_DECISION, PlacePanel, REACH_STAGE, ReachPanel } from "./roomScreens";

const PICK = "pick"; // the Decision that makes a Stage's screen the Variant grid
const REFRESH_DELAY_MS = 100; // one refresh for a burst of "changed" events

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
  const [progress, setProgress] = useState<string | null>(null);
  const [connected, setConnected] = useState(true);
  const [gameFrame, setGameFrame] = useState(false);
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
  }, [refresh]);

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
  const isReach = current === REACH_STAGE && show?.kind === "room";

  // Each user action is one Command; its findings show until the next action. They go one at a time, in the order they
  // were made: a Run straight after a `set` must see that `set`, not find its lock held.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const perform = useCallback(
    <T,>(action: () => Promise<Envelope<T>>): Promise<void> => {
      const done = queue.current.then(async () => {
        try {
          const result = await action();
          setNotice(result.findings);
          setConnected(true);
          await refresh();
        } catch {
          setConnected(false);
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
    });
  const decideMarker = useCallback(
    (marker: Record<string, unknown>) => {
      const decision = JSON.stringify({ decision: PLACE_DECISION, data: marker });
      void perform(() => call("decide", { asset, stage: current, decision }));
    },
    [asset, current, perform],
  );
  const pick = useCallback(
    (variant: string) => {
      if (!busy) void perform(() => call("pick", { asset, variant }));
    },
    [asset, busy, perform],
  );
  const importFiles = async (files: File[]) => {
    for (const file of files) await perform(() => callWithFile("import", { asset }, "file", file));
  };
  const step = useCallback(
    (command: "undo" | "redo") => {
      if (!busy) void perform(() => call(command, { asset, stage: current }));
    },
    [asset, busy, current, perform],
  );

  // The job exists once it reaches the front of the queue, and only then can it be cancelled.
  const run = async () => {
    const id = crypto.randomUUID();
    await perform(() => {
      setJob(id);
      return call("run", { asset }, id);
    });
    setJob(null);
    setProgress(null);
  };
  const accept = () => void perform(() => call("accept", { asset, stage: current }));

  const names = show?.stages.map((entry) => entry.stage) ?? [];
  const following = current ? names[names.indexOf(current) + 1] : undefined;

  const variants = show?.variants;
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const typing = event.target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(event.target.tagName);
      if (typing) return;
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

  function open(assetId: string, stageName: string | null) {
    setAsset(assetId);
    setStage(stageName);
    setNotice([]);
  }

  // Children's effects run first, so the canvas has already started on the new Stage's image when this one focuses it.
  const jumpTo = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    if (jumpTo.current) canvas.current?.focus(jumpTo.current.x, jumpTo.current.y);
    jumpTo.current = null;
  });

  function jump(finding: Finding) {
    const { stage: where, x, y } = finding.position ?? {};
    if (x != null && y != null) jumpTo.current = { x, y };
    if (where && where !== current) setStage(where);
    else setRefocus((count) => count + 1);
  }

  const stageChecks = data.checks.filter((finding) => (finding.position?.stage ?? current) === current);
  // Reach has no image of its own, and the Body walks on the mapped room that `place` is made on.
  const reachImage = isReach ? show?.stages.find((entry) => entry.stage === "place")?.input_image : null;
  const image = detail?.image ?? detail?.input_image ?? reachImage ?? null;
  const after = image ? fileUrl(image, imageVersion) : null;
  const before = detail?.image && detail.input_image ? fileUrl(detail.input_image, imageVersion) : null;

  const primary = job ? (
    <button className="primary" data-testid="cancel" onClick={() => void cancelJob(job)}>
      Cancel
    </button>
  ) : detail?.status === "needs-review" ? (
    <button className="primary" data-testid="accept" onClick={accept}>
      Accept ▶
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
        <button className="title" data-testid="home" onClick={() => setAsset(null)}>
          Kiripix
        </button>
        <span className="project">{data.status?.project}</span>
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
            {next && next.stage === detail.stage && (next.owner_action || next.command) && (
              <p className="hint" data-testid="next-hint">
                {next.owner_action ?? <code>{next.command}</code>}
              </p>
            )}
            {isPlace && (
              <PlacePanel
                key={asset}
                canvas={canvas}
                detail={detail}
                status={data.status}
                decide={decideMarker}
                disabled={busy}
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
            {!isSource && image && (
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
            {notice.length > 0 && (
              <>
                <h2>Last Command</h2>
                <FindingList findings={notice} onJump={jump} testid="notice" />
              </>
            )}
            {progress && <p className="hint" data-testid="progress">{progress}</p>}
            <div className="primary-action">{primary}</div>
          </>
        ) : data.problems.length === 0 ? (
          <p className="hint">Choose an Asset to see its Stages.</p>
        ) : null}
        {data.problems.length > 0 && (
          <>
            <h2>Can't read the Project</h2>
            <FindingList findings={data.problems} onJump={jump} testid="problems" />
          </>
        )}
      </aside>
      <footer>
        {show && <StageBar stages={show.stages} selected={current} onSelect={setStage} />}
      </footer>
    </div>
  );
}
