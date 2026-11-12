// The flows of ticket 0181 (spec §11): a sprite's import, its frame strip and its pivot. The frames are made-up figures of
// 16 x 20 px, as in tests/cli/test_sprite.py; no Runner and no Blender are used.

import { readFileSync } from "node:fs";
import { crc32 } from "node:zlib";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, png, test, type Studio } from "./harness";

const SPRITE = "sprite.npc";
const WORK = (studio: Studio) => join(studio.cwd, "assets", "sprite", "npc", "work");

type Colour = [number, number, number, number];

// The figure at a pixel of a 16 x 20 cell: small, with 1 px legs; `hop` lifts it, `tone` tells Directions apart.
function pixel(col: number, row: number, tone: number, hop = 0): Colour {
  const at = row + hop;
  if (col >= 6 && col <= 8 && at >= 2 && at < 5) return [200, 60 + tone, 60, 255];
  if (col >= 5 && col <= 9 && at >= 5 && at < 12) return [100, 30 + tone, 120, 255];
  if ((col === 6 || col === 8) && at >= 12 && at < 15) return [200, 60 + tone, 60, 255];
  return [0, 0, 0, 0];
}

function figure(tone: number, hop = 0): Buffer {
  return png(16, 20, (x, y) => pixel(x, y, tone, hop));
}

// One row per Direction, `frames` across.
function sheet(rows: number, frames: number): Buffer {
  return png(16 * frames, 20 * rows, (x, y) => pixel(x % 16, y % 20, 40 * Math.floor(y / 20)));
}

// A ZIP of stored (uncompressed) entries, so the test needs no library.
function zip(entries: Record<string, Buffer>): Buffer {
  const parts: Buffer[] = [];
  const central: Buffer[] = [];
  let offset = 0;
  for (const [name, data] of Object.entries(entries)) {
    const label = Buffer.from(name, "utf-8");
    const sum = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(sum, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(label.length, 26);
    parts.push(local, label, data);
    const entry = Buffer.alloc(46);
    entry.writeUInt32LE(0x02014b50, 0);
    entry.writeUInt16LE(20, 4);
    entry.writeUInt16LE(20, 6);
    entry.writeUInt32LE(sum, 16);
    entry.writeUInt32LE(data.length, 20);
    entry.writeUInt32LE(data.length, 24);
    entry.writeUInt16LE(label.length, 28);
    entry.writeUInt32LE(offset, 42);
    central.push(entry, label);
    offset += local.length + label.length + data.length;
  }
  const directory = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(Object.keys(entries).length, 8);
  end.writeUInt16LE(Object.keys(entries).length, 10);
  end.writeUInt32LE(directory.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, directory, end]);
}

const WORDS: [string, number][] = [["south", 0], ["west", 40], ["north", 80], ["east", 120]];

// PixelLab's layout: animations/<clip>/<direction word>/frame_NNN.png.
function pixellab(clip: string, frames: number, hops: (frame: number) => number): Buffer {
  const entries: Record<string, Buffer> = {};
  for (const [word, tone] of WORDS) {
    for (let frame = 0; frame < frames; frame++) {
      entries[`animations/${clip}/${word}/frame_${String(frame).padStart(3, "0")}.png`] = figure(tone, hops(frame));
    }
  }
  return zip(entries);
}

async function open(page: Page, studio: Studio, stage: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${SPRITE}`).click();
  await page.getByTestId(`stage-${stage}`).click();
}

// Runs the Stages the screens show; the export has no Godot project here and stops, which these flows don't read.
async function runIt(page: Page): Promise<void> {
  await page.getByTestId("run").click();
  await expect(page.getByTestId("run")).toHaveCount(0, { timeout: 40_000 });
}

const view = (page: Page) => page.getByTestId("frame-view");
const fit = (studio: Studio) => JSON.parse(readFileSync(join(WORK(studio), "fit", "fit.json"), "utf-8")) as { pivots: Record<string, number[]> };

test.setTimeout(120_000);

test("a ZIP is dropped, listed with its name, and its frames show on fit; clips step and Directions switch by key", async ({ page, studio }) => {
  studio.kiripix("new", "sprite", "npc");
  await page.goto(studio.home);
  await page.getByTestId(`asset-${SPRITE}`).click();
  await expect(page.getByTestId("sprite-frames-screen")).toBeVisible();
  await expect(page.getByTestId("sheets-empty")).toBeVisible();

  await page.getByTestId("sheet-drop-input").setInputFiles({ name: "npc.zip", mimeType: "application/zip", buffer: pixellab("breathing-idle", 2, (frame) => frame) });
  await expect(page.getByTestId("sheet-list")).toContainText("npc.zip");
  await expect(page.getByTestId("sheet-list")).toContainText("ZIP, 8 PNGs");
  await runIt(page);
  await expect(page.getByTestId("clip-summary")).toContainText("breathing_idle");

  await page.getByTestId("stage-fit").click();
  await expect(view(page)).toBeVisible();
  await expect(view(page)).toHaveAttribute("data-clip", "breathing_idle");
  await expect(view(page)).toHaveAttribute("data-direction", "s");
  await expect(page.locator(".frame-thumb")).toHaveCount(2);

  // A 4-direction sprite has no nw: its button is grey and its key does nothing.
  await expect(page.getByTestId("direction-nw")).toBeDisabled();
  await expect(page.getByTestId("direction-e")).toBeEnabled();
  await page.keyboard.press("Numpad7");
  await expect(view(page)).toHaveAttribute("data-direction", "s");
  await page.keyboard.press("Numpad6");
  await expect(view(page)).toHaveAttribute("data-direction", "e");
  await page.keyboard.press("Numpad4");
  await expect(view(page)).toHaveAttribute("data-direction", "w");
  await page.keyboard.press("Period");
  await expect(view(page)).toHaveAttribute("data-frame", "1");
  await page.keyboard.press("Comma");
  await expect(view(page)).toHaveAttribute("data-frame", "0");

  // No smoothing, and a whole-number zoom.
  const canvas = page.getByTestId("frame-canvas");
  await expect(canvas).toHaveCSS("image-rendering", "pixelated");
  await page.keyboard.press("KeyZ");
  await expect(canvas).toHaveAttribute("data-zoom", "6");
  expect(Number.isInteger(await canvas.evaluate((element) => element.getBoundingClientRect().width / (element as HTMLCanvasElement).width))).toBe(true);

  // The palette Stage shows the same strip.
  await page.getByTestId("stage-palette").click();
  await expect(page.locator(".frame-thumb")).toHaveCount(2);
});

test("a PNG sheet needs its form; the cut and a clip's playback are one decide each, and the frames show", async ({ page, studio }) => {
  studio.kiripix("new", "sprite", "npc");
  await page.goto(studio.home);
  await page.getByTestId(`asset-${SPRITE}`).click();
  await page.getByTestId("sheet-drop-input").setInputFiles({ name: "walk.png", mimeType: "image/png", buffer: sheet(4, 3) });
  await expect(page.locator("[data-testid^=sheet-form-]")).toBeVisible();
  await expect(page.getByTestId("sheet-list")).toContainText("walk.png");

  // A bad name is said, and the button waits.
  await page.getByTestId("sheet-clip").fill("Walk_S");
  await expect(page.getByTestId("sheet-problem")).toBeVisible();
  await expect(page.getByTestId("sheet-cut")).toBeDisabled();
  await page.getByTestId("sheet-clip").fill("walk");
  await page.getByTestId("sheet-frames").fill("3");
  await expect(page.getByTestId("sheet-directions")).toHaveValue("s w n e");
  await page.getByTestId("sheet-cut").click();
  await expect(page.locator("[data-testid^=sheet-cut-]")).toContainText("cut as walk: rows, s w n e, 3 frames");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  await page.getByTestId("clip-name").fill("walk");
  await page.getByTestId("clip-fps").fill("12");
  await page.getByTestId("clip-loop").uncheck();
  await page.getByTestId("clip-set").click();
  await expect(page.getByTestId("clip-decisions")).toContainText("walk: 12 frames a second, plays once");
  await runIt(page);

  await page.getByTestId("stage-fit").click();
  await expect(view(page)).toHaveAttribute("data-clip", "walk");
  await expect(page.locator(".frame-thumb")).toHaveCount(3);
  await expect(page.getByTestId("player-info")).toContainText("12 frames a second");
  await expect(page.getByTestId("player-info")).toContainText("plays once");
  await page.keyboard.press("Numpad8");
  await expect(view(page)).toHaveAttribute("data-direction", "n");
  await page.keyboard.press("Period");
  await page.keyboard.press("Period");
  await expect(view(page)).toHaveAttribute("data-frame", "2");
});

test("a Direction the sheet lacks is a finding a person can read", async ({ page, studio }) => {
  studio.kiripix("new", "sprite", "npc");
  await page.goto(studio.home);
  await page.getByTestId(`asset-${SPRITE}`).click();
  await page.getByTestId("sheet-drop-input").setInputFiles({ name: "three.png", mimeType: "image/png", buffer: sheet(3, 1) });
  await page.getByTestId("sheet-directions").fill("s w n");
  await page.getByTestId("sheet-cut").click();
  await expect(page.locator("[data-testid^=sheet-cut-]")).toBeVisible();
  await page.getByTestId("run").click();
  const finding = page.getByTestId("finding-frames.direction_missing").first();
  await expect(finding).toBeVisible({ timeout: 40_000 });
  await expect(finding).toContainText(/east|\be\b/);
});

test("a click on fit sets the pivot for the Direction, Shift for all, and Ctrl+Z undoes it", async ({ page, studio }) => {
  studio.kiripix("new", "sprite", "npc");
  studio.write("one.png", sheet(4, 1));
  const name = studio.json("import", SPRITE, "incoming/one.png", "--role", "sheet").data.sheet as string;
  studio.kiripix(
    "decide", SPRITE, "frames", "--decision",
    JSON.stringify({ decision: "sheet", data: { file: name, clip: "idle", layout: "rows", directions: ["s", "w", "n", "e"], frames: 1 } }),
  );
  studio.run(SPRITE);
  const measured = fit(studio).pivots;
  expect(measured.s).toEqual([7, 14]);

  await open(page, studio, "fit");
  await expect(view(page)).toBeVisible();
  await expect(page.getByTestId("pivot-hint")).toBeVisible();
  await expect(page.locator('.frame-box[data-pickable="true"]')).toBeVisible();
  const canvas = page.getByTestId("frame-canvas");
  const picture = () => canvas.evaluate((element: HTMLCanvasElement) => element.toDataURL());
  const before = await picture();
  await expect(page.getByTestId("frame-canvas-pivot")).toBeVisible();
  const render = JSON.parse(readFileSync(join(WORK(studio), "fit", "render.json"), "utf-8")) as { pivot: number[] };
  const cell = render.pivot;
  const zoom = 4;

  // Two pixels to the right of the measured feet, for s alone.
  await canvas.click({ position: { x: (cell[0] + 2) * zoom + 2, y: cell[1] * zoom + 2 } });
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect.poll(() => fit(studio).pivots.s).toEqual([9, 14]);
  expect(fit(studio).pivots.w).toEqual(measured.w);
  await expect.poll(picture).not.toBe(before);

  // Ctrl+Z is `undo`, and `fit` shows the old pivot again.
  await page.keyboard.press("Control+KeyZ");
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");
  await expect.poll(() => fit(studio).pivots.s).toEqual(measured.s);
  await expect.poll(picture).toBe(before);

  // With Shift every Direction takes it.
  await canvas.click({ position: { x: (cell[0] + 1) * zoom + 2, y: cell[1] * zoom + 2 }, modifiers: ["Shift"] });
  await expect.poll(() => fit(studio).pivots.e).toEqual([8, 14]);
  expect(fit(studio).pivots.n).toEqual([8, 14]);
});

test("a sheet.pivot_drift finding on a sprite jumps to its frame", async ({ page, studio }) => {
  studio.kiripix("new", "sprite", "npc");
  studio.write("idle.zip", pixellab("idle", 3, (frame) => (frame === 2 ? 1 : 0)));
  studio.kiripix("import", SPRITE, "incoming/idle.zip", "--role", "sheet");
  studio.kiripix("decide", SPRITE, "frames", "--decision", JSON.stringify({ decision: "clip", data: { name: "idle", fps: 8, loop: true, stationary: true } }));
  studio.run(SPRITE);

  await open(page, studio, "sheet");
  await expect(view(page)).toBeVisible();
  const finding = page.getByTestId("finding-sheet.pivot_drift").first();
  await expect(finding).toBeVisible();
  await page.getByTestId("direction-e").click();
  await finding.click();
  await expect(view(page)).toHaveAttribute("data-clip", "idle");
  await expect(view(page)).toHaveAttribute("data-frame", "2");
});
