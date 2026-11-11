// The flows of ticket 0115 (spec §11): a character's frame strip, onion skin, compass, Clip player and normal-map view, on the
// render, palette, finish and sheet Stages. Blender is the fake one of tests/fixtures, whose frames are flat and 78 px square.

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, png, test, type Studio } from "./harness";

const HERO = "character.hero";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");
const IDLE = { name: "idle", source: "idle", start: 0, end: 24, fps: 12, loop: true, stationary: true };
const HIT = { name: "hit", source: "walk", start: 0, end: 6, fps: 15, loop: false };

// A character built through `sheet`, with two Clips.
function sheeted(studio: Studio): void {
  studio.kiripix("new", "character", "hero");
  const variant = studio.json("import", HERO, join(CHARACTERS, "rigged.glb")).data.variant as string;
  studio.kiripix("pick", HERO, variant);
  studio.run(HERO);
  for (const data of [IDLE, HIT]) {
    studio.kiripix("decide", HERO, "clips", "--decision", JSON.stringify({ decision: "clip", data }));
  }
  studio.kiripix("set", HERO, "palette", "colors=3");
  studio.run(HERO);
}

function render(studio: Studio): string {
  return join(studio.cwd, "assets", "character", "hero", "work", "render");
}

async function open(page: Page, studio: Studio, stage: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${HERO}`).click();
  await page.getByTestId(`stage-${stage}`).click();
  await expect(page.getByTestId("frame-view")).toBeVisible();
}

test.setTimeout(120_000); // each test builds a character through `sheet` first

const view = (page: Page) => page.getByTestId("frame-view");

test("a Clip is stepped through, a Direction is chosen by the number pad, and the canvas is drawn without smoothing", async ({
  page,
  segmentingStudio: studio,
}) => {
  sheeted(studio);
  await open(page, studio, "render");
  await expect(view(page)).toHaveAttribute("data-clip", "hit");
  await expect(view(page)).toHaveAttribute("data-direction", "s");
  await expect(view(page)).toHaveAttribute("data-frame", "0");
  await expect(page.locator(".frame-thumb")).toHaveCount(4);

  await page.keyboard.press("Period");
  await page.keyboard.press("ArrowRight");
  await expect(view(page)).toHaveAttribute("data-frame", "2");
  await page.keyboard.press("Comma");
  await expect(view(page)).toHaveAttribute("data-frame", "1");
  await page.getByTestId("player-next").click();
  await expect(view(page)).toHaveAttribute("data-frame", "2");
  await page.getByTestId("frame-3").click();
  await expect(view(page)).toHaveAttribute("data-frame", "3");

  await page.keyboard.press("Numpad6");
  await expect(view(page)).toHaveAttribute("data-direction", "e");
  await page.keyboard.press("Numpad7");
  await expect(view(page)).toHaveAttribute("data-direction", "nw");
  await expect(page.getByTestId("direction-nw")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("direction-sw").click();
  await expect(view(page)).toHaveAttribute("data-direction", "sw");
  await page.keyboard.press("ArrowDown");
  await expect(view(page)).toHaveAttribute("data-clip", "idle");
  await expect(view(page)).toHaveAttribute("data-frame", "0");

  // The picture is the frame's own, scaled by a whole number, with the browser told not to smooth it.
  const canvas = page.getByTestId("frame-canvas");
  await expect(canvas).toHaveCSS("image-rendering", "pixelated");
  const drawn = await canvas.evaluate((element: HTMLCanvasElement) => {
    const pixel = element.getContext("2d")!.getImageData(1, 1, 1, 1).data;
    return { ratio: element.getBoundingClientRect().width / element.width, pixel: [...pixel] };
  });
  expect(Number.isInteger(drawn.ratio)).toBe(true);
  expect(drawn.pixel).toEqual([200, 100, 50, 255]);
  await page.keyboard.press("KeyZ");
  await expect(canvas).toHaveAttribute("data-zoom", "6");
  expect(Number.isInteger(await canvas.evaluate((element) => element.getBoundingClientRect().width / (element as HTMLCanvasElement).width))).toBe(true);
});

test("the onion skin shows the neighbouring frames faintly, and the normal map shows the normal pass", async ({
  page,
  segmentingStudio: studio,
}) => {
  sheeted(studio);
  // Frame 0 and 2 of idle/s are solid, frame 1 is empty, so what lies under frame 1 is only the onion skin.
  const solid = png(78, 78, () => [10, 200, 30, 255]);
  const empty = png(78, 78, () => [0, 0, 0, 0]);
  const frames = join(render(studio), "color", "idle", "s");
  writeFileSync(join(frames, "000.png"), solid);
  writeFileSync(join(frames, "001.png"), empty);
  writeFileSync(join(frames, "002.png"), solid);
  await open(page, studio, "render");
  await page.getByTestId("clip-tab-idle").click();
  await page.getByTestId("frame-1").click();
  const canvas = page.getByTestId("frame-canvas");
  const alpha = () => canvas.evaluate((element: HTMLCanvasElement) => element.getContext("2d")!.getImageData(5, 5, 1, 1).data[3]);

  await expect.poll(alpha).toBe(0);
  await page.keyboard.press("KeyO");
  await expect(view(page)).toHaveAttribute("data-onion", "true");
  await expect.poll(alpha).toBeGreaterThan(40);
  expect(await alpha()).toBeLessThan(160);
  await page.getByTestId("onion").uncheck();
  await expect.poll(alpha).toBe(0);

  await page.getByTestId("frame-0").click();
  await page.keyboard.press("KeyN");
  await expect(view(page)).toHaveAttribute("data-normal", "true");
  await expect
    .poll(() => canvas.evaluate((element: HTMLCanvasElement) => [...element.getContext("2d")!.getImageData(1, 1, 1, 1).data]))
    .toEqual([128, 128, 255, 255]);
  await page.keyboard.press("KeyN");
  await expect(view(page)).toHaveAttribute("data-normal", "false");
});

test("a Clip plays at its frame rate, loops when it loops, and stops at the end when it doesn't", async ({ page, segmentingStudio: studio }) => {
  sheeted(studio);
  await open(page, studio, "palette");
  await expect(page.getByTestId("player-info")).toContainText("15 frames a second");
  await expect(page.getByTestId("player-info")).toContainText("plays once");

  // `hit`: 4 frames at 15 a second, from its first to its last, take 3 / 15 of a second, once.
  const began = Date.now();
  await page.getByTestId("player-play").click();
  await expect(view(page)).toHaveAttribute("data-playing", "true");
  await expect(view(page)).toHaveAttribute("data-playing", "false", { timeout: 3000 });
  const took = Date.now() - began;
  await expect(view(page)).toHaveAttribute("data-frame", "3");
  expect(took).toBeGreaterThan(180);
  expect(took).toBeLessThan(1500);

  // Playing it again starts from the first frame; Space pauses it.
  await page.keyboard.press("Space");
  await expect(view(page)).toHaveAttribute("data-playing", "true");
  await page.keyboard.press("Space");
  await expect(view(page)).toHaveAttribute("data-playing", "false");

  // `idle` loops: after a while it is still playing, and has gone round to a frame that isn't the last.
  await page.getByTestId("clip-tab-idle").click();
  await expect(page.getByTestId("player-info")).toContainText("loops");
  await page.getByTestId("player-play").click();
  const seen = new Set<string>();
  const until = Date.now() + 1500;
  while (Date.now() < until) {
    seen.add((await view(page).getAttribute("data-frame")) ?? "");
    await page.waitForTimeout(30);
  }
  await expect(view(page)).toHaveAttribute("data-playing", "true");
  expect(seen.size).toBeGreaterThan(8);
  await page.getByTestId("player-play").click();
  await expect(view(page)).toHaveAttribute("data-playing", "false");
});

test("a sheet.pivot_drift finding jumps to its Clip, Direction and frame, and the sheet is read from the atlas", async ({
  page,
  segmentingStudio: studio,
}) => {
  sheeted(studio);
  // As in the Python test: finish's render.json has one idle/s frame whose pivot has moved.
  const path = join(studio.cwd, "assets", "character", "hero", "work", "finish", "render.json");
  const document = JSON.parse(readFileSync(path, "utf-8"));
  document.clips.find((entry: { name: string }) => entry.name === "idle").directions.s[2].pivot = [40.0, 72.0];
  writeFileSync(path, JSON.stringify(document));
  studio.run(HERO);

  await open(page, studio, "sheet");
  await expect(view(page)).toHaveAttribute("data-clip", "hit");
  const finding = page.getByTestId("finding-sheet.pivot_drift");
  await expect(finding).toBeVisible();
  await page.getByTestId("direction-e").click(); // somewhere else, to show the jump moves
  await finding.click();
  await expect(view(page)).toHaveAttribute("data-clip", "idle");
  await expect(view(page)).toHaveAttribute("data-direction", "s");
  await expect(view(page)).toHaveAttribute("data-frame", "2");
  await expect(page.getByTestId("frame-2")).toHaveAttribute("aria-pressed", "true");

  // The frame comes out of the colour atlas, at integer zoom, and the normal atlas shows on the normal key.
  const canvas = page.getByTestId("frame-canvas");
  await expect.poll(() => canvas.evaluate((element: HTMLCanvasElement) => element.getContext("2d")!.getImageData(39, 40, 1, 1).data[3])).toBe(255);
  await page.keyboard.press("KeyN");
  await expect(view(page)).toHaveAttribute("data-normal", "true");
  await expect(canvas).toHaveCSS("image-rendering", "pixelated");
});

test("an agent's new frames show on the open screen", async ({ page, segmentingStudio: studio }) => {
  sheeted(studio);
  await open(page, studio, "finish");
  await expect(page.locator(".frame-thumb")).toHaveCount(4);
  studio.kiripix("decide", HERO, "clips", "--decision", JSON.stringify({ decision: "clip", data: { ...HIT, name: "slash", end: 3 } }));
  studio.run(HERO);
  await expect(page.getByTestId("clip-tab-slash")).toBeVisible();
});
