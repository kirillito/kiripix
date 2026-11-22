// The Project's rows (ticket 0374, spec §11): the cheap list at once, then each row's status and queue from `status` and `queue` by
// Asset ID, the rows on screen first and the rest in the background in chunks. It only asks and keeps the answers; every value
// is the Commands'. Server side, an Asset already worked out is remembered (ticket 0373), so asking a row again costs little.

import { call, type Finding, type ListAnswer, type ListRow, type QueueData, type QueueStop, type StageState, type StatusAnswer, type StatusData } from "./api";

const VISIBLE_CHUNK = 30; // rows asked together when they are on screen
const BACKGROUND_CHUNK = 60; // rows asked together in the background
const QUEUE_CHUNK = 100;
const CONCURRENCY = 2;
const SETTLE_MS = 50; // the first list renders, and reports what is on screen, before the background starts

let tokens = 0;

// The Asset an event's path is in: `assets/<kind>/<name>/...` is `<kind>.<name>`.
export function assetOfPath(path: string): string | null {
  const parts = path.split("/");
  return parts[0] === "assets" && parts.length >= 3 ? `${parts[1]}.${parts[2]}` : null;
}

interface Bucket {
  stops: QueueStop[];
  fixable: QueueData["agent_fixable"];
}

export class Rows {
  list: ListRow[] = [];
  private known = new Set<string>();
  private settled = false; // the first list has been drawn
  project = "";
  private listProblems: Finding[] = [];
  private stages = new Map<string, StageState[]>();
  private fresh = new Set<string>();
  private inflight = new Set<string>();
  private sweep = new Set<string>();
  private floor = 0; // the number of the latest invalidation: an answer asked before it may be older than a change
  private seq = 0;
  private token: string | undefined;
  private visible = new Map<string, string[]>();
  private forgetting = new Set<string>(); // rows `serve` is to forget the next time they are asked (the window's focus)
  private active = 0;
  private idle: (() => void)[] = [];
  private first: (() => void)[] = [];
  private buckets = new Map<string, Bucket>();
  private queueFindings = new Map<string, Finding[]>();
  private queueMatch: string | null = null;
  private queueSeq = 0;
  private queueAsked = new Map<string, number>(); // each row's newest `queue` call: an older one answering later is not kept
  private statusProblems = new Map<string, Finding>();
  asked = 0; // status requests made (for the specs and the strip)

  constructor(
    private readonly changed: () => void,
    private readonly failed: () => void,
  ) {}

  // Why the list or a row can't be read.
  get problems(): Finding[] {
    return [...this.listProblems, ...this.statusProblems.values()];
  }

  // A full refresh (Reload, a reconnect): one new token for all its calls. The first call `serve` sees with it drops what it
  // remembers. The page's first read sends none: `serve` keeps its memory in step with what Kiripix wrote (ticket 0373).
  newToken(): void {
    this.token = `${Date.now().toString(36)}-${++tokens}`;
  }

  private withToken<T extends object>(input: T): T & { refresh?: string } {
    return this.token ? { ...input, refresh: this.token } : input;
  }

  // The cheap list: every row from the `asset.toml` files, at once.
  async read(): Promise<void> {
    const answer = await call<ListAnswer>("assets", this.withToken({}));
    this.listProblems = answer.findings;
    if (!answer.data) throw new Error("assets");
    this.project = answer.data.project;
    this.list = answer.data.assets;
    this.known = new Set(this.list.map((row) => row.asset));
    for (const id of [...this.stages.keys()]) if (!this.known.has(id)) this.stages.delete(id);
    this.changed();
  }

  // The rows may have changed: the ones named (null: all) are asked again, and so is what is on screen; the others when they come in view.
  invalidate(): void {
    this.fresh.clear();
    this.floor = ++this.seq;
  }

  // The rows' status now, from the list and what has answered.
  snapshot(): StatusData | null {
    if (this.project === "" && this.list.length === 0) return null;
    return {
      project: this.project,
      assets: this.list.map((row) => ({ ...row, stages: this.stages.get(row.asset) ?? null })),
    };
  }

  // The Assets whose rows a change to `ids` may change: those that name one of them (a base, a body) and those they name.
  related(ids: string[]): string[] {
    const named = new Set(ids);
    const found = new Set(ids);
    for (const row of this.list) {
      if ((row.base && named.has(row.base)) || (row.body && named.has(row.body))) found.add(row.asset);
      if (named.has(row.asset)) {
        if (row.base) found.add(row.base);
        if (row.body) found.add(row.body);
      }
    }
    return [...found];
  }

  // The rows on screen now, every list's.
  shown(): string[] {
    return [...new Set([...this.visible.values()].flat())];
  }

  // The window got the focus back: a file of these rows may have changed outside Kiripix, so the next ask of each tells `serve`
  // to forget it (its `forget`), and every other row is kept.
  forgetOnce(ids: string[]): void {
    for (const id of ids) this.forgetting.add(id);
  }

  // What the lists show now, by source (the Asset list, the board): these rows are asked first.
  see(source: string, ids: string[]): void {
    const before = this.visible.get(source);
    if (before && before.length === ids.length && before.every((id, at) => id === ids[at])) return;
    this.visible.set(source, ids);
    this.pump();
  }

  // Ask the status of `ids` (null: every row), the rows on screen first. Resolves when every row asked has an answer.
  // `onFirst` is called once the first answer has landed (or there is nothing to ask), so other reads can start after it.
  async start(ids: string[] | null, onFirst: () => void): Promise<void> {
    if (ids === null) this.statusProblems.clear();
    if (!this.settled) await new Promise((done) => setTimeout(done, SETTLE_MS));
    this.settled = true;
    const known = this.known;
    for (const row of this.list) if (ids === null || !this.stages.has(row.asset)) this.sweep.add(row.asset);
    if (ids) for (const id of ids) if (known.has(id)) this.sweep.add(id);
    const done = new Promise<void>((resolve) => this.idle.push(resolve));
    this.first.push(onFirst);
    this.pump();
    return done;
  }

  private wanted(): string[] {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const ids of this.visible.values())
      for (const id of ids)
        if (!seen.has(id) && !this.fresh.has(id) && !this.inflight.has(id) && this.known.has(id)) {
          seen.add(id);
          out.push(id);
        }
    return out;
  }

  private pump(): void {
    while (this.active < CONCURRENCY) {
      let chunk = this.wanted().slice(0, VISIBLE_CHUNK);
      if (chunk.length === 0) {
        for (const row of this.list) {
          if (chunk.length >= BACKGROUND_CHUNK) break;
          if (!this.sweep.has(row.asset)) continue;
          if (this.fresh.has(row.asset)) this.sweep.delete(row.asset);
          else if (!this.inflight.has(row.asset)) chunk.push(row.asset);
        }
        for (const id of [...this.sweep]) if (!this.known.has(id)) this.sweep.delete(id);
      }
      if (chunk.length === 0) break;
      void this.ask(chunk);
    }
    if (this.active === 0 && this.wanted().length === 0 && !this.pendingSweep()) {
      this.release(this.first);
      this.release(this.idle);
    }
  }

  private pendingSweep(): boolean {
    for (const id of this.sweep) if (!this.fresh.has(id) && this.known.has(id)) return true;
    return false;
  }

  private release(waiting: (() => void)[]): void {
    for (const done of waiting.splice(0)) done();
  }

  private async ask(chunk: string[]): Promise<void> {
    this.active += 1;
    const start = this.seq;
    for (const id of chunk) {
      this.inflight.add(id);
      this.sweep.delete(id);
    }
    this.asked += 1;
    try {
      const forget = chunk.filter((id) => this.forgetting.has(id));
      for (const id of forget) this.forgetting.delete(id);
      const input = forget.length ? { assets: chunk, forget } : { assets: chunk };
      const answer = await call<StatusAnswer>("status", this.withToken(input));
      for (const row of answer.data?.assets ?? []) {
        this.stages.set(row.asset, row.stages);
        if (start >= this.floor) this.fresh.add(row.asset);
        else this.sweep.add(row.asset); // asked before a change: once more
      }
      for (const finding of answer.findings) if (finding.code !== "asset.not_found") this.statusProblems.set(`${finding.code} ${finding.message}`, finding);
      this.changed();
    } catch {
      this.failed();
    } finally {
      for (const id of chunk) this.inflight.delete(id);
      this.active -= 1;
      this.release(this.first);
      this.pump();
    }
  }

  // The queue of `ids` (null: every row) for `match`, in chunks, whose counts are summed here. Published once, when all have answered.
  async queue(ids: string[] | null, match: string, isAlive: () => boolean): Promise<{ data: QueueData; findings: Finding[] } | null> {
    if (this.queueMatch !== match) {
      this.buckets.clear();
      this.queueFindings.clear();
      this.queueMatch = match;
      ids = null;
    }
    const known = this.known;
    const asking = (ids ?? this.list.map((row) => row.asset)).filter((id) => known.has(id));
    for (let at = 0; at < asking.length; at += QUEUE_CHUNK) {
      if (!isAlive()) return null;
      const asked = asking.slice(at, at + QUEUE_CHUNK);
      const mine = ++this.queueSeq;
      for (const id of asked) this.queueAsked.set(id, mine);
      const answer = await call<QueueData>("queue", this.withToken(match ? { assets: asked, match } : { assets: asked }));
      if (!answer.data) throw new Error("queue");
      if (this.queueMatch !== match) return null; // the match changed meanwhile: its own read publishes
      const chunk = asked.filter((id) => this.queueAsked.get(id) === mine);
      if (chunk.length === 0) continue;
      for (const id of chunk) this.buckets.set(id, { stops: [], fixable: [] });
      for (const key of [...this.queueFindings.keys()]) if (key.startsWith("chunk:") || chunk.includes(key)) this.queueFindings.delete(key);
      for (const stop of answer.data.stops) this.buckets.get(stop.asset)?.stops.push(stop);
      for (const entry of answer.data.agent_fixable) this.buckets.get(entry.asset)?.fixable.push(entry);
      for (const finding of answer.findings) {
        if (finding.code === "asset.not_found") continue;
        if (finding.position?.asset && !chunk.includes(finding.position.asset)) continue; // a row a newer call has asked again
        const key = finding.position?.asset ?? `chunk:${chunk[0]}`;
        this.queueFindings.set(key, [...(this.queueFindings.get(key) ?? []), finding]);
      }
    }
    for (const id of [...this.buckets.keys()]) if (!known.has(id)) this.buckets.delete(id);
    return this.queueSnapshot();
  }

  private queueSnapshot(): { data: QueueData; findings: Finding[] } {
    const stops: QueueStop[] = [];
    const fixable: QueueData["agent_fixable"] = [];
    const clear: string[] = [];
    for (const row of this.list) {
      const bucket = this.buckets.get(row.asset);
      if (!bucket) continue;
      stops.push(...bucket.stops);
      fixable.push(...bucket.fixable);
      if (bucket.stops.length === 0 && bucket.fixable.length === 0) clear.push(row.asset);
    }
    const count = (type: QueueStop["type"]) => stops.filter((stop) => stop.type === type).length;
    const agent = fixable.reduce((sum, entry) => sum + entry.count, 0);
    const seen = new Set<string>();
    const findings = [...this.queueFindings.values()].flat().filter((finding) => {
      const key = `${finding.code} ${finding.message}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    return {
      data: {
        stops,
        agent_fixable: fixable,
        counts: { review: count("review"), input: count("input"), finding: count("finding"), total: stops.length, agent_fixable: agent, assets_clear: clear },
      },
      findings,
    };
  }
}
