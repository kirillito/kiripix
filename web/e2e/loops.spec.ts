// Ticket 0191 (spec §6.1 and §11): the loops screen, against a real `kiripix serve`. A region is flooded, two colours are picked
// with the eyedropper, the cycle and its timing are set, and the preview plays by the Loop's `sequence`. Every action is one
// Command (a Decision, then a rebuild of the Stage while "rebuild" is on).

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, layeredRoom, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const RED = "#ff004d"; // the floor's left half
const BLUE = "#1d2b53"; // its right half

async function open(page: Page, studio: Studio): Promise<void> {
  layeredRoom(studio);
  studio.run(ROOM);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-loops").click();
  await expect(page.getByTestId("stage-title")).toHaveText("loops");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("loop-panel")).toBeVisible();
}

async function pixel(page: Page, x: number, y: number): Promise<{ x: number; y: number }> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  return { x: box.x + left + (x + 0.5) * zoom, y: box.y + top + (y + 0.5) * zoom };
}

async function clickPixel(page: Page, x: number, y: number): Promise<void> {
  const at = await pixel(page, x, y);
  await page.mouse.click(at.x, at.y);
}

function journal(studio: Studio): { name: string; data: Record<string, unknown> }[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "loops")!.decisions;
}

function built(studio: Studio): { loops: Record<string, unknown>[] } {
  return JSON.parse(readFileSync(join(studio.cwd, "assets", "room", "alley", "work", "loops", "loops.json"), "utf-8")) as { loops: Record<string, unknown>[] };
}

// A Loop on the floor's left half: flooded, then the floor's two colours picked with the eyedropper.
async function floorCycle(page: Page): Promise<void> {
  await page.getByTestId("loop-new").fill("floor_glow");
  await page.getByTestId("loop-add").click();
  await expect(page.getByTestId("loop-floor_glow")).toBeVisible();
  await page.getByTestId("loop-opacity").fill("0");
  await page.keyboard.press("f");
  await clickPixel(page, 4, 24);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await page.keyboard.press("i");
  await clickPixel(page, 4, 24);
  await expect(page.getByTestId("cycle-colour-0")).toBeVisible();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-lit", new RegExp(`^${RED}:\\d+$`));
  await clickPixel(page, 44, 24);
  await expect(page.getByTestId("cycle-colour-1")).toBeVisible();
}

test("a region is flooded, two colours are picked, and the preview plays the Loop by its sequence", async ({ page, studio }) => {
  await open(page, studio);
  await floorCycle(page);

  const decisions = journal(studio);
  expect(decisions.map((entry) => entry.name)).toEqual(["loop", "flood", "cycle", "cycle"]); // each click is one Decision
  expect(decisions[1].data).toMatchObject({ loop: "floor_glow", x: 4, y: 24 });
  expect(decisions[3].data).toMatchObject({ loop: "floor_glow", colours: [RED, BLUE] });

  await page.getByTestId("mode-rotate").click();
  await page.getByTestId("loop-ticks").fill("6");
  await page.getByTestId("loop-ticks").press("Enter");
  await expect(page.getByTestId("loop-list")).toContainText("2 frames, 12 ticks");
  const loop = built(studio).loops[0];
  expect(loop).toMatchObject({ id: "floor_glow", form: "cycle", mode: "rotate", colours: [RED, BLUE], sequence: [[0, 6], [1, 6]], ticks: 12 });
  expect(journal(studio).at(-1)).toMatchObject({ name: "timing", data: { loop: "floor_glow", ticks: 6 } });

  // Paused shows frame 0, which is the room; playing steps whole ticks by the sequence.
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-loop-playing", "false");
  await expect(canvas).toHaveAttribute("data-loop-frames", "floor_glow:0");
  await page.getByTestId("loop-step").click();
  await expect(canvas).toHaveAttribute("data-loop-tick", "1");
  await page.getByTestId("loop-play").click();
  await expect(canvas).toHaveAttribute("data-loop-playing", "true");
  await expect.poll(async () => Number(await canvas.getAttribute("data-loop-tick"))).toBeGreaterThan(12);
  const seen = new Set<string>();
  for (let n = 0; n < 40; n++) {
    seen.add((await canvas.getAttribute("data-loop-frames"))!);
    await page.waitForTimeout(25);
  }
  expect([...seen].sort()).toEqual(["floor_glow:0", "floor_glow:1"]);
  await page.getByTestId("loop-play").click();
  await expect(canvas).toHaveAttribute("data-loop-tick", "0");
  await expect(canvas).toHaveAttribute("data-loop-frames", "floor_glow:0");

  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT });
  await page.keyboard.press("Control+z"); // one `undo` takes the timing back
  await expect(page.getByTestId("decision-count")).toHaveText("4 Decision(s)");
});

test("a flicker fast enough to trip loop.flash shows the error, and accept stays disabled until the timing changes", async ({ page, studio }) => {
  // The screen the Loop covers a quarter of (WCAG 2.3.1) is the project resolution: a small one makes the floor big enough.
  const toml = join(studio.cwd, "kiripix.toml");
  writeFileSync(toml, readFileSync(toml, "utf-8").replace(/resolution\s*=\s*\[.*?\]/, "resolution = [40, 30]"), "utf-8");
  await open(page, studio);
  await floorCycle(page);

  await page.getByTestId("timing-flicker").click();
  await expect(page.getByTestId("loop-seed")).toBeVisible();
  await page.getByTestId("loop-flicker-mean").fill("1");
  await page.getByTestId("loop-flicker-mean").press("Enter");
  await page.getByTestId("loop-flicker-spread").fill("0");
  await page.getByTestId("loop-flicker-spread").press("Enter");
  await expect.poll(() => journal(studio).at(-1)).toMatchObject({ name: "timing", data: { flicker: { mean_ticks: 1, spread: 0 } } });

  const flash = page.getByTestId("loop-finding-loop.flash");
  await expect(flash).toBeVisible();
  await expect(flash).toHaveAttribute("data-severity", "error");
  await expect(page.getByTestId("accept")).toBeDisabled();

  await page.getByTestId("loop-reroll").click(); // a new seed is one more Decision
  await expect(page.getByTestId("decision-count")).toHaveText("7 Decision(s)");

  await page.getByTestId("timing-even").click();
  await page.getByTestId("loop-ticks").fill("30");
  await page.getByTestId("loop-ticks").press("Enter");
  await expect(page.getByTestId("loop-finding-loop.flash")).toHaveCount(0);
  await expect(page.getByTestId("accept")).toHaveCount(0);
});

test("an agent's cycle shows in the screen, and a seam finding's fix is one timing Decision from a button", async ({ page, studio }) => {
  await open(page, studio);
  await floorCycle(page);
  // An agent sets a cycle over the whole ramp while the screen is open: the wrap jumps, and the screen follows the change.
  const ramp = ["#000000", "#1d2b53", "#5f574f", "#83769c", "#c2c3c7", "#fff1e8"];
  const decision = JSON.stringify({ decision: "cycle", data: { loop: "floor_glow", colours: ramp } });
  studio.kiripix("decide", ROOM, "loops", "--decision", decision);
  await expect(page.getByTestId("cycle-colour-5")).toBeVisible();
  studio.kiripix("run", ROOM, "loops");

  const seam = page.getByTestId("loop-finding-loop.seam");
  await expect(seam).toBeVisible();
  await expect(seam).toHaveAttribute("data-severity", "warning");
  const before = journal(studio).length;
  await page.getByTestId("loop-fix-loop.seam").click();
  await expect(page.getByTestId("loop-finding-loop.seam")).toHaveCount(0);
  expect(journal(studio)).toHaveLength(before + 1);
  expect(journal(studio).at(-1)).toMatchObject({ name: "timing", data: { loop: "floor_glow", pingpong: true } });
  await expect(page.getByTestId("loop-pingpong")).toBeChecked();
});

// Ticket 0196: a frame Loop. A `sway` on a Layer from the sliders; a kit written, two painted frames imported, a tick count per frame.

async function framesLoop(page: Page, id: string, layer: string): Promise<void> {
  await page.getByTestId("loop-new").fill(id);
  await page.getByTestId("loop-new-form").selectOption("frames");
  await page.getByTestId("loop-add").click();
  await expect(page.getByTestId(`loop-${id}`)).toBeVisible();
  await page.getByTestId("loop-layer").selectOption(layer);
  await expect(page.getByTestId("source-op")).toBeVisible();
}

test("a sway Loop on a Layer is set from its sliders, the preview plays it, and loops.json has it", async ({ page, studio }) => {
  await open(page, studio);
  await framesLoop(page, "lamp_sway", "lamp");
  await page.getByTestId("op-sway").click();
  await expect(page.getByTestId("op-amplitude")).toBeVisible();
  await page.getByTestId("op-amplitude").fill("2");
  await page.getByTestId("op-frames").fill("5");
  await expect.poll(() => journal(studio).filter((entry) => entry.name === "frames").at(-1)?.data).toMatchObject({
    loop: "lamp_sway",
    source: "op",
    op: "sway",
    params: { amplitude: 2, frames: 5 },
  });
  await expect(page.getByTestId("loop-list")).toContainText("5 frames");
  expect(built(studio).loops[0]).toMatchObject({ id: "lamp_sway", form: "frames", op: "sway", layer: "lamp", frames: 5 });

  await page.getByTestId("tool-anchor").click(); // click the anchor row on the canvas
  await clickPixel(page, 33, 8);
  await expect(page.getByTestId("anchor-row")).toHaveText("row 8");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loop-anchor", "8");

  const canvas = page.getByTestId("canvas");
  await page.getByTestId("loop-play").click();
  await expect(canvas).toHaveAttribute("data-loop-playing", "true");
  const seen = new Set<string>();
  for (let n = 0; n < 60; n++) {
    seen.add((await canvas.getAttribute("data-loop-frames"))!);
    await page.waitForTimeout(25);
  }
  expect(seen.size).toBeGreaterThan(1);
  await page.getByTestId("loop-play").click();

  // A frame alone, with the one before it faint.
  await page.getByTestId("frame-show-2").click();
  await expect(canvas).toHaveAttribute("data-loop-inspect", "lamp_sway:2");
  await expect(page.getByTestId("frame-0")).toContainText("the room's");
  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT });
});

test("sway is disabled on the plate, with a way to the layers screen", async ({ page, studio }) => {
  await open(page, studio);
  await framesLoop(page, "on_plate", "plate");
  await expect(page.getByTestId("op-sway")).toBeDisabled();
  await expect(page.getByTestId("op-no-fill")).toBeVisible();
  await page.getByTestId("open-layers").click();
  await expect(page.getByTestId("stage-title")).toHaveText("layers");
});

test("a kit is written, two painted frames are imported, a frame gets its own ticks, and the stray one has a badge", async ({ page, studio }) => {
  await open(page, studio);
  await framesLoop(page, "lamp_paint", "lamp");
  await page.getByTestId("op-shimmer").click();
  await page.getByTestId("loop-opacity").fill("0");
  await page.keyboard.press("f");
  await clickPixel(page, 33, 6); // the lamp is the Loop's region
  await expect(page.getByTestId("loop-list")).toContainText("frames");
  await expect.poll(() => built(studio).loops.length).toBe(1);
  await page.getByTestId("source-kit").click();
  await page.getByTestId("kit-folder").fill("kits/lamp");
  await page.getByTestId("kit-frames").fill("3");
  await page.getByTestId("kit-write").click();
  await expect(page.getByTestId("kit-path")).toContainText("kits");
  const [, , width, height] = built(studio).loops[0].box as number[];

  // The Owner paints over copies of frame_001 and frame_002: one is clean, the other has a pixel off the palette.
  const kit = join(studio.cwd, "kits", "lamp");
  const paint = (stray: boolean) => png(width, height, (x, y) => (stray && x === 1 && y === 1 ? [250, 0, 77, 255] : [255, 0, 77, 255]));
  writeFileSync(join(kit, "frame_001.png"), paint(false));
  writeFileSync(join(kit, "frame_002.png"), paint(true));
  await page.getByTestId("kit-import").click();
  await expect(page.getByTestId("loop-list")).toContainText("3 frames");
  await expect(page.getByTestId("frame-2")).toBeVisible();
  await expect(page.getByTestId("frame-badge-2-loop.off_palette")).toBeVisible();
  await expect(page.getByTestId("frame-badge-1-loop.off_palette")).toHaveCount(0);

  await page.getByTestId("frame-ticks-2").fill("12");
  await page.getByTestId("frame-ticks-2").press("Enter");
  await expect.poll(() => journal(studio).filter((entry) => entry.name === "timing").at(-1)?.data.ticks).toEqual([expect.any(Number), expect.any(Number), 12]);
  await expect(page.getByTestId("loop-list")).toContainText(/, \d+ ticks/);
  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT.replace(/\.png$/, "-kit.png") });
});
