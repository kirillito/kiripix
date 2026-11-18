// The flows of ticket 0284 (spec §11): a character's named points (ticket 0237) drawn on its frames, as a 1-px cross at the
// recorded pixel, hollow when behind the body. Blender is the fake one of tests/fixtures, which puts each point 10 px right of
// the pivot per its place in the list, 30 px above it, and `hidden` in the direction `n`.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./harness";

const HERO = "character.hero";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");

test.setTimeout(120_000);

test("each frame has a cross at the recorded pixel, a hidden point is hollow, and the toggle hides them", async ({ page, segmentingStudio: studio }) => {
  studio.kiripix("new", "character", "hero");
  const variant = studio.json("import", HERO, join(CHARACTERS, "rigged.glb")).data.variant as string;
  studio.kiripix("pick", HERO, variant);
  studio.run(HERO);
  const clip = { name: "hit", source: "walk", start: 0, end: 6, fps: 15, loop: false };
  studio.kiripix("decide", HERO, "clips", "--decision", JSON.stringify({ decision: "clip", data: clip }));
  studio.kiripix("set", HERO, "render", "points=hand_r@hand_r");
  studio.run(HERO);

  const record = JSON.parse(readFileSync(join(studio.cwd, "assets", "character", "hero", "work", "render", "render.json"), "utf-8"));
  const frames = record.clips.find((c: { name: string }) => c.name === "hit").directions;

  await page.goto(studio.home);
  await page.getByTestId(`asset-${HERO}`).click();
  await page.getByTestId("stage-render").click();
  await expect(page.getByTestId("frame-view")).toBeVisible();

  // One cross per frame, at the pixel the record holds: in the big view and in every thumbnail.
  const crosses = page.locator('[data-testid^="thumb-"][data-testid$="-point-hand_r"]');
  await expect(crosses).toHaveCount(frames.s.length);
  for (const frame of frames.s) {
    const place = frame.points.hand_r;
    const mark = page.getByTestId(`thumb-${frame.index}-point-hand_r`);
    await expect(mark).toHaveAttribute("data-x", String(Math.floor(place.x)));
    await expect(mark).toHaveAttribute("data-y", String(Math.floor(place.y)));
    await expect(mark).toHaveAttribute("data-hidden", "false");
    await expect(mark).toHaveAttribute("title", "hand_r");
  }
  await expect(page.getByTestId("frame-canvas-point-hand_r")).toHaveAttribute("data-x", String(Math.floor(frames.s[0].points.hand_r.x)));

  // The point follows the frames as the Clip plays or steps.
  await page.getByTestId("player-next").click();
  await expect(page.getByTestId("frame-view")).toHaveAttribute("data-frame", "1");
  await expect(page.getByTestId("frame-canvas-point-hand_r")).toHaveAttribute("data-y", String(Math.floor(frames.s[1].points.hand_r.y)));

  // Behind the body, the point is hollow.
  await page.getByTestId("frame-view").screenshot({ path: join(import.meta.dirname, "..", "shots", "0284-points.png") });
  await page.getByTestId("direction-n").click();
  await expect(page.getByTestId("frame-canvas-point-hand_r")).toHaveAttribute("data-hidden", "true");
  await expect(page.getByTestId("frame-canvas-point-hand_r")).toHaveClass(/point-hollow/);

  await page.getByTestId("points-view").uncheck();
  await expect(page.locator('[data-testid$="-point-hand_r"]')).toHaveCount(0);
  await page.keyboard.press("KeyH");
  await expect(page.getByTestId("frame-canvas-point-hand_r")).toBeVisible();
});

test("on the sheet the points are at the pivot plus the recorded offset", async ({ page, segmentingStudio: studio }) => {
  studio.kiripix("new", "character", "hero");
  const variant = studio.json("import", HERO, join(CHARACTERS, "rigged.glb")).data.variant as string;
  studio.kiripix("pick", HERO, variant);
  studio.run(HERO);
  const clip = { name: "idle", source: "idle", start: 0, end: 24, fps: 12, loop: true, stationary: true };
  studio.kiripix("decide", HERO, "clips", "--decision", JSON.stringify({ decision: "clip", data: clip }));
  studio.kiripix("set", HERO, "render", "points=hand_r@hand_r");
  studio.kiripix("set", HERO, "palette", "colors=3");
  studio.run(HERO);

  const sheet = JSON.parse(readFileSync(join(studio.cwd, "assets", "character", "hero", "work", "sheet", "sheet.json"), "utf-8"));
  const first = sheet.clips[0].directions.s[0];

  await page.goto(studio.home);
  await page.getByTestId(`asset-${HERO}`).click();
  await page.getByTestId("stage-sheet").click();
  const mark = page.getByTestId("frame-canvas-point-hand_r");
  await expect(mark).toHaveAttribute("data-x", String(sheet.pivot.x + first.points.hand_r.x));
  await expect(mark).toHaveAttribute("data-y", String(sheet.pivot.y + first.points.hand_r.y));
});
