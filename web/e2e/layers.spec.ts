// The flows of ticket 0053 (spec §11): the layers screen, against a real `kiripix serve` on a temporary Project. SAM 2 and the
// inpainter are the fake Runners of tests/fixtures, as in the Python tests, so nothing is downloaded and no GPU is needed.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const RED: [number, number, number, number] = [255, 0, 77, 255];
const DARK: [number, number, number, number] = [29, 43, 83, 255];
const WHITE: [number, number, number, number] = [255, 255, 255, 255];

// The target pixels of the block in the full image: x 20..27, y 10..17 (a 2 px Source cell each).
const inBlock = (x: number, y: number) => x >= 40 && x < 56 && y >= 20 && y < 36;
const ground = (x: number): [number, number, number, number] => (Math.floor(x / 2) < 24 ? RED : DARK);

function fullImage(): Buffer {
  return png(96, 64, (x, y) => (inBlock(x, y) ? WHITE : ground(x)));
}

function plateImage(width = 96, height = 64): Buffer {
  return png(width, height, (x) => ground(x));
}

function builtRoom(studio: Studio, full = art(24)): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", full));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-layers").click();
  await expect(page.getByTestId("stage-title")).toHaveText("layers");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("layers-panel")).toBeVisible();
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

async function dragPixel(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const start = await pixel(page, ...from);
  const end = await pixel(page, ...to);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move((start.x + end.x) / 2, (start.y + end.y) / 2);
  await page.mouse.move(end.x, end.y);
  await page.mouse.up();
}

interface Journal {
  name: string;
  data: Record<string, unknown>;
}

function layersStage(studio: Studio): { status: string; decisions: Journal[]; outputs: string[] } {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; status: string; decisions: Journal[]; outputs: string[] }[];
  return stages.find((entry) => entry.stage === "layers")!;
}

function runnerCalls(studio: Studio): number {
  const file = join(studio.cwd, "runner-calls.jsonl");
  return existsSync(file) ? readFileSync(file, "utf-8").split("\n").filter(Boolean).length : 0;
}

// Everything under decisions/ and the journal, with sizes and times: a write would change it.
function journalFiles(studio: Studio): string {
  const folder = join(studio.cwd, "assets", "room", "alley");
  const walk = (directory: string): string[] =>
    readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? walk(path) : [`${path} ${statSync(path).size} ${statSync(path).mtimeMs}`];
    });
  return [...walk(join(folder, "decisions")), readFileSync(join(folder, "history.jsonl"), "utf-8")].join("\n");
}

test("hover records nothing, a click records one Decision, the primary action leads to needs-review, Accept to done, and the Layer toggles", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");
  const before = journalFiles(studio);

  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } }); // out of the field, so the letters are shortcuts
  await page.keyboard.press("c");
  const at = await pixel(page, 20, 16);
  await page.mouse.move(at.x - 3, at.y);
  await page.mouse.move(at.x, at.y);
  await expect.poll(async () => Number(await canvas.getAttribute("data-preview"))).toBeGreaterThan(0);
  await page.waitForTimeout(300);
  expect(journalFiles(studio)).toBe(before);
  expect(layersStage(studio).decisions).toHaveLength(0);

  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(layersStage(studio).decisions).toHaveLength(1);
  expect(layersStage(studio).decisions[0]).toMatchObject({ name: "click", data: { x: 20, y: 16, layer: "lamp", positive: true } });
  expect(runnerCalls(studio)).toBe(0); // the Owner re-runs the Runner, a click doesn't

  await page.getByTestId("rerun").click();
  await expect(page.getByTestId("accept")).toBeVisible();
  expect(layersStage(studio).status).toBe("needs-review");
  expect(runnerCalls(studio)).toBeGreaterThan(0);
  await expect(page.getByTestId("layer-lamp")).toBeVisible();
  await expect(canvas).toHaveAttribute("data-layers-shown", "lamp");

  await page.getByTestId("accept").click();
  await expect(page.getByTestId("accept")).toHaveCount(0);
  expect(layersStage(studio).status).toBe("done");
  expect(layersStage(studio).outputs.some((path) => path.endsWith("layer.lamp.png"))).toBe(true);

  await page.getByTestId("show-lamp").uncheck();
  await expect(canvas).toHaveAttribute("data-layers-shown", "");
  await page.getByTestId("show-plate").uncheck();
  await expect(canvas).toHaveAttribute("data-plate-shown", "false");
  await page.getByTestId("show-hole").check();
  await expect.poll(async () => await canvas.getAttribute("data-masks")).toMatch(/hole:[1-9]/);
  await page.getByTestId("show-lamp").check();
  await expect(canvas).toHaveAttribute("data-layers-shown", "lamp");
});

test("shift-click subtracts, and a trim stroke is one Decision on release", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.getByLabel("Re-run the Runner after each click").check();
  await page.keyboard.press("c");

  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("accept")).toBeVisible();
  await page.keyboard.down("Shift");
  await clickPixel(page, 20, 16);
  await page.keyboard.up("Shift");
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(layersStage(studio).decisions[1]).toMatchObject({ name: "click", data: { layer: "lamp", positive: false } });

  await page.getByTestId("accept").click();
  await expect(page.getByTestId("accept")).toHaveCount(0);
  await page.keyboard.press("t");
  await expect(page.getByTestId("tool-trim")).toHaveAttribute("aria-pressed", "true");
  await dragPixel(page, [15, 14], [25, 14]);

  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  const made = layersStage(studio).decisions;
  expect(made.filter((entry) => entry.name === "trim")).toHaveLength(1);
  expect(made[2]).toMatchObject({ name: "trim", data: { layer: "lamp", radius: 2 } });
  expect((made[2].data.points as number[][]).length).toBeGreaterThan(1);
});

test("a Shift-click on a Layer no click has lifted yet records nothing and says why", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.keyboard.press("c");

  await page.keyboard.down("Shift");
  await clickPixel(page, 20, 16);
  await page.keyboard.up("Shift");
  await expect(page.getByTestId("layers-notice")).toHaveText(
    "Nothing to take away from: click an object to lift it into lamp first.",
  );

  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(layersStage(studio).decisions[0]).toMatchObject({ name: "click", data: { layer: "lamp", positive: true } });
});

test("Shift-hover tints the part of the segment on the Layer, and a Shift-click takes it off", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");
  const preview = async () => Number(await canvas.getAttribute("data-preview"));
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.getByLabel("Re-run the Runner after each click").check();
  await page.keyboard.press("c");
  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("accept")).toBeVisible();
  await expect(page.getByTestId("layer-lamp")).toBeVisible();

  const at = await pixel(page, 26, 16);
  await page.mouse.move(at.x - 3, at.y);
  await page.mouse.move(at.x, at.y);
  await expect.poll(preview).toBeGreaterThan(0);
  const whole = await preview();
  await page.keyboard.down("Shift");
  await expect.poll(preview).toBeLessThan(whole);
  await expect.poll(preview).toBeGreaterThan(0);

  const away = await pixel(page, 44, 16); // over nothing on the Layer
  await page.mouse.move(away.x - 3, away.y);
  await page.mouse.move(away.x, away.y);
  await expect.poll(preview).toBe(0);
  await page.mouse.move(at.x - 3, at.y);
  await page.mouse.move(at.x, at.y);
  await expect.poll(preview).toBeGreaterThan(0);
  await page.mouse.click(at.x, at.y);
  await page.keyboard.up("Shift");

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(layersStage(studio).decisions[1]).toMatchObject({ name: "click", data: { x: 26, y: 16, layer: "lamp", positive: false } });
});

test("a Plate image gives Layers with no Runner call, and the stage is done", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio, fullImage());
  await open(page, studio);

  await page.getByTestId("plate-import-input").setInputFiles({ name: "plate.png", mimeType: "image/png", buffer: plateImage() });
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(layersStage(studio).decisions[0].name).toBe("plate");

  await page.getByTestId("layer-id").fill("crate");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.keyboard.press("c");
  await expect(page.getByTestId("layers-panel")).toContainText("difference");
  await page.getByLabel("Re-run the Runner after each click").check();
  await clickPixel(page, 24, 14);

  await expect(page.getByTestId("layer-state-crate")).toHaveAttribute("data-state", "lifted");
  expect(layersStage(studio).status).toBe("done");
  await expect(page.getByTestId("accept")).toHaveCount(0);
  expect(runnerCalls(studio)).toBe(0);
  expect(layersStage(studio).outputs.some((path) => path.endsWith("layer.crate.png"))).toBe(true);
});

test("a Plate image of the wrong size needs input, and the screen shows next's text", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio, fullImage());
  await open(page, studio);

  await page.getByTestId("plate-import-input").setInputFiles({ name: "small.png", mimeType: "image/png", buffer: plateImage(48, 32) });

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect(page.getByTestId("next-hint")).toContainText("Plate image of the Source's size");
  expect(runnerCalls(studio)).toBe(0);
});
