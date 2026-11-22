// The flows of ticket 0374 (spec §11): the Project opens from the cheap list at once, a long list draws only the rows in view and
// asks `status` for them first, and a change asks only for the rows it names. A Project of 300 light Assets: only their `asset.toml`.

import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOMS = 240;
const PROPS = 60;
// In ID order the props come first, then the rooms.
const FIRST = "prop.p000";
const LAST = `room.r${String(ROOMS - 1).padStart(3, "0")}`;

function lightAssets(studio: Studio, rooms = ROOMS, props = PROPS): void {
  const write = (kind: string, name: string, params: string) => {
    const folder = join(studio.cwd, "assets", kind, name);
    mkdirSync(folder, { recursive: true });
    writeFileSync(join(folder, "asset.toml"), `schema_version = 1\nkind = "${kind}"\n\n[params]\n${params}\n[stages]\n`);
  };
  for (let at = 0; at < rooms; at++) write("room", `r${String(at).padStart(3, "0")}`, 'view = "top"\n');
  for (let at = 0; at < props; at++) write("prop", `p${String(at).padStart(3, "0")}`, "");
}

// Every `status` request the page makes, with the Assets it asked for.
function watchStatus(page: Page): { asked: string[][]; files: string[]; lists: number } {
  const log = { asked: [] as string[][], files: [] as string[], lists: 0 };
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path === "/api/status") log.asked.push((JSON.parse(request.postData() ?? "{}") as { assets?: string[] }).assets ?? ["*"]);
    else if (path === "/api/assets") log.lists += 1;
    else if (path.startsWith("/files/")) log.files.push(decodeURIComponent(path));
  });
  return log;
}

test("the list's first rows show before any status answers, and a long list draws only the rows in view", async ({ page, studio }) => {
  lightAssets(studio);
  let release: () => void = () => undefined;
  const held = new Promise<void>((done) => (release = done));
  await page.route("**/api/status", async (route) => {
    await held;
    await route.continue();
  });
  const log = watchStatus(page);
  await page.goto(studio.home);
  await expect(page.getByTestId(`asset-${FIRST}`)).toBeVisible();
  // No status has answered: every row shows its quiet placeholder.
  await expect(page.getByTestId(`asset-${FIRST}`).locator("[data-pending]")).toHaveCount(1);
  expect(await page.locator("nav.assets button.asset").count()).toBeLessThan(80);
  await expect(page.getByTestId(`asset-${LAST}`)).toHaveCount(0);
  expect(log.asked.length).toBeGreaterThan(0);
  expect(log.asked[0].length).toBeLessThanOrEqual(30); // the rows in view first, in a chunk of their own
  expect(log.asked[0]).toContain(FIRST);
  release();
  await expect(page.getByTestId(`asset-${FIRST}`).locator(".glyph[data-status]")).toHaveCount(1);
  await expect(page.getByTestId("work-strip")).toHaveCount(0);
  // The rest were asked in the background, in chunks, and no row was asked for twice by the sweep.
  const asked = log.asked.flat();
  expect(new Set(asked).size).toBe(ROOMS + PROPS);
  expect(log.asked.every((ids) => ids.length <= 60)).toBe(true);
  await page.screenshot({ path: "shots/0374-list.png" });
});

test("a scroll asks for the rows it reaches before the background gets to them", async ({ page, studio }) => {
  lightAssets(studio);
  await page.route("**/api/status", async (route) => {
    await new Promise((done) => setTimeout(done, 400));
    await route.continue();
  });
  const log = watchStatus(page);
  await page.goto(studio.home);
  await expect(page.getByTestId(`asset-${FIRST}`)).toBeVisible();
  await page.locator("nav.assets").evaluate((nav) => nav.scrollTo(0, nav.scrollHeight));
  await expect(page.getByTestId(`asset-${LAST}`)).toBeVisible();
  await expect(page.getByTestId(`asset-${LAST}`).locator(".glyph[data-status]")).toHaveCount(1);
  const reaching = log.asked.findIndex((ids) => ids.includes(LAST));
  expect(reaching).toBeGreaterThanOrEqual(0);
  expect(log.asked[reaching].length).toBeLessThanOrEqual(30); // a request for the rows in view, not the sweep's chunk
  expect(reaching).toBeLessThan(5);
  // The rows off screen drew nothing and fetched no image.
  expect(await page.locator("nav.assets button.asset").count()).toBeLessThan(80);
  expect(log.files).toEqual([]);
  await expect(page.getByTestId("work-strip")).toHaveCount(0);
});

test("a change asks again only for the rows it names and the rows in view", async ({ page, studio }) => {
  lightAssets(studio);
  const log = watchStatus(page);
  await page.goto(studio.home);
  await expect(page.getByTestId(`asset-${FIRST}`).locator(".glyph[data-status]")).toHaveCount(1);
  await expect(page.getByTestId("work-strip")).toHaveCount(0);
  await page.waitForTimeout(500);
  const before = log.asked.length;
  const lists = log.lists;
  // An agent's files in two Assets' folders: one in view, one far off screen.
  for (const named of ["prop.p001", LAST]) studio.importVariant(named, `${named}.png`, art(24));
  await page.waitForTimeout(2500);
  const since = log.asked.slice(before);
  expect(since.length).toBeGreaterThan(0);
  const asked = since.flat();
  expect(asked).toContain("prop.p001");
  expect(asked).toContain(LAST); // named, so asked though off screen
  expect(asked.length).toBeLessThan(120); // the visible window and the named rows: not the 300
  expect(asked).not.toContain("room.r120");
  expect(log.lists).toBeGreaterThan(lists); // the cheap list is read again: a row may be new
});

test("a thumbnail in the district view is fetched only when it is in view", async ({ page, studio }) => {
  studio.room();
  lightAssets(studio, 30, 0);
  studio.kiripix("pick", "room.alley", studio.importVariant("room.alley", "a.png", art(24)));
  studio.run("room.alley");
  await page.goto(`${studio.home.replace("#", "?district=room.*#")}`);
  const thumb = page.getByTestId("district-thumb-room.alley");
  await expect(thumb).toHaveAttribute("loading", "lazy");
});
