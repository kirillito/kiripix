// Ticket 0210 (spec §6.1 and §11): the loops screen's follow-ups, against a real `kiripix serve`. A held Loop shows its region and the
// other Loops play; a Loop is renamed and another removed, each one Decision, and `undo` takes the removal back; several frames and
// the kit's `kit.json` are dropped on the strip and go in as one `import --loop`.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, layeredRoom, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const RED = "#ff004d";
const BLUE = "#1d2b53";
const ORANGE = "#ffa300";

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

async function clickPixel(page: Page, x: number, y: number): Promise<void> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  await page.mouse.click(box.x + left + (x + 0.5) * zoom, box.y + top + (y + 0.5) * zoom);
}

function journal(studio: Studio): { name: string; data: Record<string, unknown> }[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "loops")!.decisions;
}

function built(studio: Studio): { loops: Record<string, unknown>[] } {
  return JSON.parse(readFileSync(join(studio.cwd, "assets", "room", "alley", "work", "loops", "loops.json"), "utf-8")) as { loops: Record<string, unknown>[] };
}

const ids = (studio: Studio) => built(studio).loops.map((loop) => loop.id as string).sort();

// An agent's Decisions, as the CLI records them; the Stage is built after them (it may exit 2 for a finding).
function decide(studio: Studio, name: string, data: Record<string, unknown>): void {
  studio.kiripix("decide", ROOM, "loops", "--decision", JSON.stringify({ decision: name, data }));
}

function build(studio: Studio): void {
  try {
    studio.kiripix("run", ROOM, "loops");
  } catch {
    // A held Loop makes `run` exit 2.
  }
}

// Two complete cycle Loops: the floor's left half, and the lamp.
function twoLoops(studio: Studio): void {
  decide(studio, "loop", { loop: "floor_glow" });
  decide(studio, "flood", { loop: "floor_glow", x: 4, y: 24 });
  decide(studio, "cycle", { loop: "floor_glow", colours: [RED, BLUE] });
  decide(studio, "loop", { loop: "lamp_glow" });
  decide(studio, "flood", { loop: "lamp_glow", x: 33, y: 6 });
  decide(studio, "cycle", { loop: "lamp_glow", colours: [ORANGE, RED] });
}

test("a region flooded before any colour shows at once, and a complete Loop plays beside the held one", async ({ page, studio }) => {
  await open(page, studio);
  decide(studio, "loop", { loop: "floor_glow" });
  decide(studio, "flood", { loop: "floor_glow", x: 4, y: 24 });
  decide(studio, "cycle", { loop: "floor_glow", colours: [RED, BLUE] });
  build(studio);
  await expect(page.getByTestId("loop-list")).toContainText("2 frames");

  await page.getByTestId("loop-new").fill("lamp_glow");
  await page.getByTestId("loop-add").click();
  await expect(page.getByTestId("loop-lamp_glow")).toBeVisible();
  await page.getByTestId("loop-opacity").fill("40");
  await page.keyboard.press("f");
  await clickPixel(page, 33, 6); // the flood, before a colour is picked

  const canvas = page.getByTestId("canvas");
  await expect(page.getByTestId("loop-held-lamp_glow")).toBeVisible();
  await expect(page.getByTestId("loop-list")).toContainText("held");
  await expect(page.getByTestId("loop-finding-loop.held")).toBeVisible();
  await expect(canvas).toHaveAttribute("data-masks", /region:[1-9]\d* /); // the region is drawn from its region.png
  const held = built(studio).loops.find((loop) => loop.id === "lamp_glow")!;
  expect(held).toMatchObject({ frames: 0 });
  expect(held.held).toBeTruthy();
  expect(journal(studio).map((entry) => entry.name)).toEqual(["loop", "flood", "cycle", "loop", "flood"]); // the click was one Decision

  // The preview plays the complete Loop; the held one plays nothing.
  await expect(page.getByTestId("accept")).toBeDisabled();
  await page.getByTestId("loop-play").click();
  await expect(canvas).toHaveAttribute("data-loop-playing", "true");
  const seen = new Set<string>();
  for (let n = 0; n < 60; n++) {
    seen.add((await canvas.getAttribute("data-loop-frames"))!);
    await page.waitForTimeout(25);
  }
  expect([...seen].sort()).toEqual(["floor_glow:0", "floor_glow:1"]);
  await page.getByTestId("loop-play").click();
  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT });
});

test("a Loop is renamed and another removed, each one Decision, and undo restores the removed one", async ({ page, studio }) => {
  await open(page, studio);
  twoLoops(studio);
  build(studio);
  await page.reload();
  await expect(page.getByTestId("loop-floor_glow")).toBeVisible();
  await expect(page.getByTestId("loop-lamp_glow")).toBeVisible();
  expect(ids(studio)).toEqual(["floor_glow", "lamp_glow"]);
  const before = journal(studio).length;

  await page.getByTestId("loop-floor_glow").click();
  await page.getByTestId("loop-rename").fill("ground_glow");
  await page.getByTestId("loop-rename-go").click();
  await expect(page.getByTestId("loop-ground_glow")).toBeVisible();
  await expect(page.getByTestId("loop-floor_glow")).toHaveCount(0);
  await expect.poll(() => ids(studio)).toEqual(["ground_glow", "lamp_glow"]);
  expect(journal(studio)).toHaveLength(before + 1);
  expect(journal(studio).at(-1)).toMatchObject({ name: "rename", data: { loop: "floor_glow", to: "ground_glow" } });
  expect(built(studio).loops.find((loop) => loop.id === "ground_glow")).toMatchObject({ frames: 2 });

  await page.getByTestId("loop-lamp_glow").click();
  await page.getByTestId("loop-remove").click();
  await expect(page.getByTestId("loop-lamp_glow")).toHaveCount(0);
  await expect.poll(() => ids(studio)).toEqual(["ground_glow"]);
  expect(journal(studio)).toHaveLength(before + 2);
  expect(journal(studio).at(-1)).toMatchObject({ name: "remove", data: { loop: "lamp_glow" } });

  await page.keyboard.press("Control+z"); // one `undo` takes the removal back
  await expect(page.getByTestId("loop-lamp_glow")).toBeVisible();
  await expect.poll(() => ids(studio)).toEqual(["ground_glow", "lamp_glow"]);
  expect(journal(studio)).toHaveLength(before + 1);
  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT.replace(/\.png$/, "-rename.png") });
});

test("a rename to a Look's or another Loop's ID is refused, and the reason shows beside the list", async ({ page, studio }) => {
  await open(page, studio);
  twoLoops(studio);
  build(studio);
  await page.reload();
  await expect(page.getByTestId("loop-lamp_glow")).toBeVisible();
  const before = journal(studio).length;
  await page.getByTestId("loop-lamp_glow").click();
  await page.getByTestId("loop-rename").fill("floor_glow");
  await page.getByTestId("loop-rename-go").click();
  await expect(page.getByTestId("loop-refusal-loop.id_taken")).toBeVisible();
  expect(journal(studio)).toHaveLength(before);
});

// The game's Manifest of the room, as an export leaves it, listing `loops` as exported: their IDs are frozen (spec §9). Written
// here rather than exported, as an export needs a room every Check passes; the refusal reads only the Manifest.
function exported(studio: Studio, loops: string[]): void {
  mkdirSync(join(studio.cwd, "game", "kiripix", "manifest"), { recursive: true });
  writeFileSync(join(studio.cwd, "game", "project.godot"), "config_version=5\n");
  const settings = join(studio.cwd, "kiripix.toml");
  writeFileSync(settings, readFileSync(settings, "utf-8").replace('# project = "C:/Workspace/my-game"   # the Godot project to export into', 'project = "game"'));
  const manifest = { schema_version: 2, kiripix_version: "0", asset: ROOM, exported: true, counter: 1, ids: { markers: [], layers: [], masks: [], loops }, files: {} };
  writeFileSync(join(studio.cwd, "game", "kiripix", "manifest", `${ROOM}.json`), JSON.stringify(manifest));
}

test("a rename of an exported Loop is refused inline with export.id_frozen, and nothing is recorded", async ({ page, studio }) => {
  await open(page, studio);
  twoLoops(studio);
  build(studio);
  exported(studio, ["floor_glow"]);
  await page.reload();
  await expect(page.getByTestId("loop-floor_glow")).toBeVisible();
  const before = journal(studio).length;
  await page.getByTestId("loop-floor_glow").click();
  await page.getByTestId("loop-rename").fill("ground_glow");
  await page.getByTestId("loop-rename-go").click();
  await expect(page.getByTestId("loop-refusal-export.id_frozen")).toBeVisible();
  await expect(page.getByTestId("loop-refusal-export.id_frozen")).toContainText("floor_glow");
  await expect(page.getByTestId("loop-floor_glow")).toBeVisible();
  await expect(page.getByTestId("loop-ground_glow")).toHaveCount(0);
  expect(journal(studio)).toHaveLength(before);
});

test("two frames and the kit.json dropped on the strip go in as one import and show as thumbnails", async ({ page, studio }) => {
  await open(page, studio);
  decide(studio, "loop", { loop: "lamp_paint", form: "frames", layer: "lamp" });
  decide(studio, "flood", { loop: "lamp_paint", x: 33, y: 6 });
  build(studio);
  studio.kiripix("loop", "kit", ROOM, "lamp_paint", "kits/lamp", "--frames", "3");
  const [, , width, height] = built(studio).loops.find((loop) => loop.id === "lamp_paint")!.box as number[];
  const paint = (stray: boolean) => png(width, height, (x, y) => (stray && x === 1 && y === 1 ? [255, 163, 0, 255] : [255, 0, 77, 255]));
  studio.write("frame_001.png", paint(false));
  studio.write("frame_002.png", paint(true));
  studio.write("kit.json", readFileSync(join(studio.cwd, "kits", "lamp", "kit.json")));

  await page.reload();
  await page.getByTestId("loop-lamp_paint").click();
  await expect(page.getByTestId("frame-drop")).toBeVisible();
  const files = ["frame_002.png", "frame_001.png", "kit.json"].map((name) => ({ name, bytes: [...readFileSync(join(studio.cwd, "incoming", name))] }));
  const before = journal(studio).length;
  await page.getByTestId("frame-drop").evaluate((element, dropped) => {
    const data = new DataTransfer();
    for (const file of dropped) data.items.add(new File([new Uint8Array(file.bytes)], file.name, { type: file.name.endsWith(".json") ? "application/json" : "image/png" }));
    element.dispatchEvent(new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true }));
  }, files);

  await expect(page.getByTestId("loop-list")).toContainText("3 frames");
  await expect(page.getByTestId("frame-1")).toBeVisible();
  await expect(page.getByTestId("frame-2")).toBeVisible();
  await expect(page.getByTestId("frame-1").locator("canvas")).toBeVisible();
  await expect(page.getByTestId("frame-2").locator("canvas")).toBeVisible();
  const added = journal(studio).slice(before);
  expect(added.map((entry) => entry.name)).toEqual(["kit"]); // one import, one Decision
  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT.replace(/\.png$/, "-drop.png") });
});
