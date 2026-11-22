// The flows of ticket 0369 (spec §11): a refresh asks at once, once per action, and only for what changed. The request log is
// `page.on("request")`; the changes are a CLI as an agent runs it, and a file written by hand, which Kiripix never reports.

import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";
const OTHER = "room.beta";

interface Hit {
  at: number;
  what: string; // a Command ("show") or a file ("files/assets/room/alley/…png")
  asset: string | null;
  answered: number | null;
}

// Every request the page makes to a Command or the file route, with when it was asked and when its answer came.
function watch(page: Page): { hits: Hit[]; since: (from: number) => Hit[] } {
  const hits: Hit[] = [];
  const byRequest = new Map<unknown, Hit>();
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname.slice(1);
    let hit: Hit | null = null;
    if (path.startsWith("api/") && !path.startsWith("api/events") && !path.startsWith("api/jobs")) {
      let asset: string | null = null;
      let what = path.slice(4);
      try {
        const input = JSON.parse(request.postData() ?? "{}") as { asset?: string; name?: string };
        asset = input.asset ?? null;
        if (what === "probe" && input.name) what = `probe/${input.name}`;
      } catch {
        // A file upload: no asset to name.
      }
      hit = { at: Date.now(), what: what, asset, answered: null };
    } else if (path.startsWith("files/")) {
      hit = { at: Date.now(), what: decodeURIComponent(path + new URL(request.url()).search), asset: null, answered: null };
    }
    if (hit) {
      hits.push(hit);
      byRequest.set(request, hit);
    }
  });
  page.on("response", (response) => {
    const hit = byRequest.get(response.request());
    if (hit) hit.answered = Date.now();
  });
  return { hits, since: (from) => hits.slice(from) };
}

function commands(hits: Hit[], name: string): Hit[] {
  return hits.filter((hit) => hit.what === name);
}

async function settle(page: Page): Promise<void> {
  await expect(page.getByTestId("work-strip")).toHaveCount(0);
  await page.waitForTimeout(1500); // longer than the watch's tick and the page's delay, so a refresh the event causes has started
}

// A room, built through its first Stage, with its first Variant picked.
function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
}

function otherRoom(studio: Studio): void {
  studio.kiripix("new", "room", "beta", "--view", "top");
}

function imageOf(studio: Studio, stage: string): string {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; image: string | null }[];
  return stages.find((entry) => entry.stage === stage)!.image!;
}

test("opening an Asset asks for everything it shows before the first answer", async ({ page, studio }) => {
  builtRoom(studio);
  await page.goto(studio.home);
  await expect(page.getByTestId(`asset-${ROOM}`)).toBeVisible();
  await settle(page);
  const log = watch(page);
  await page.getByTestId(`asset-${ROOM}`).click();
  await expect(page.getByTestId("stage-title")).toBeVisible();
  await settle(page);
  const calls = ["show", "next", "check", "probe/style"].map((name) => commands(log.hits, name).find((hit) => hit.asset === ROOM || name === "probe/style")!);
  for (const call of calls) expect(call, "each of the Asset's calls is asked").toBeTruthy();
  const firstAnswer = Math.min(...calls.map((call) => call.answered!));
  for (const call of calls) expect(call.at, `${call.what} was asked before any answered`).toBeLessThanOrEqual(firstAnswer);
});

test("one Decision on the open Asset gives one refresh", async ({ page, studio }) => {
  studio.room();
  studio.importVariant(ROOM, "a.png", art(24));
  const second = studio.importVariant(ROOM, "b.png", art(10));
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-source").click();
  await expect(page.getByTestId(`variant-${second}`)).toBeVisible();
  await settle(page);
  const log = watch(page);
  await page.getByTestId(`variant-${second}`).click();
  await expect(page.getByTestId(`variant-${second}`)).toHaveAttribute("aria-pressed", "true");
  await settle(page);
  expect(commands(log.hits, "pick").length).toBe(1);
  for (const name of ["status", "queue", "show", "next", "check"]) expect(commands(log.hits, name).length, `${name} asked once`).toBe(1);
});

test("a CLI decision on another Asset asks for the list, not for the open Asset", async ({ page, studio }) => {
  builtRoom(studio);
  otherRoom(studio);
  const variant = studio.importVariant(OTHER, "c.png", art(24));
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-fit").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await settle(page);
  const log = watch(page);
  // The list's own answer after the pick: the other room's source is no longer waiting for a Variant.
  const listed = page.waitForResponse(async (response) => {
    if (!response.url().endsWith("/api/status")) return false;
    const body = (await response.json()) as { data: { assets: { asset: string; stages: { stage: string; status: string }[] }[] } };
    return body.data.assets.find((entry) => entry.asset === OTHER)?.stages.find((entry) => entry.stage === "source")?.status !== "needs-input";
  });
  studio.kiripix("pick", OTHER, variant);
  await listed;
  await expect(page.getByTestId(`asset-${OTHER}`)).toBeVisible();
  await settle(page);
  expect(commands(log.hits, "status").length).toBeGreaterThanOrEqual(1);
  expect(commands(log.hits, "queue").length).toBeGreaterThanOrEqual(1);
  for (const name of ["show", "next", "check"]) {
    expect(commands(log.hits, name).filter((hit) => hit.asset === ROOM), `${name} of the open Asset`).toHaveLength(0);
  }
  expect(log.hits.filter((hit) => hit.what.startsWith("files/assets/room/alley")), "the open Asset's images").toHaveLength(0);
});

test("a CLI run of a Stage of the open Asset updates its image and its checks", async ({ page, studio }) => {
  builtRoom(studio);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-fit").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await settle(page);
  const log = watch(page);
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "b.png", art(10)));
  studio.run(ROOM);
  await expect.poll(() => commands(log.hits, "check").filter((hit) => hit.asset === ROOM).length).toBeGreaterThanOrEqual(1);
  const image = imageOf(studio, "fit");
  await expect.poll(() => log.hits.filter((hit) => hit.what.startsWith(`files/${image}`)).length).toBeGreaterThanOrEqual(1);
  expect(commands(log.hits, "show").filter((hit) => hit.asset === ROOM).length).toBeGreaterThanOrEqual(1);
});

test("a file changed by hand shows after Reload, and after the window gets the focus back", async ({ page, studio }) => {
  builtRoom(studio);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-fit").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await settle(page);
  const image = imageOf(studio, "fit");
  const served: Buffer[] = [];
  page.on("response", (response) => {
    if (new URL(response.url()).pathname.slice(1) === `files/${encodeURI(image)}`) void response.body().then((body) => served.push(body));
  });
  const log = watch(page);

  const written = art(30);
  writeFileSync(join(studio.cwd, image), written);
  await page.waitForTimeout(1500);
  expect(log.hits.filter((hit) => hit.what.startsWith(`files/${image}`)), "nothing reports a hand edit").toHaveLength(0);
  await page.screenshot({ path: "shots/0369-reload.png" });
  await page.getByTestId("reload").click();
  await expect.poll(() => served.some((body) => body.equals(written))).toBe(true);

  const again = art(5);
  writeFileSync(join(studio.cwd, image), again);
  await page.waitForTimeout(5200); // the throttle: the window reads again at most every few seconds
  await page.evaluate(() => {
    window.dispatchEvent(new Event("blur"));
    window.dispatchEvent(new Event("focus"));
  });
  await expect.poll(() => served.some((body) => body.equals(again))).toBe(true);
});
