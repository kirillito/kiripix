// The flows of ticket 0082 (spec §11): finding your way around a room larger than the canvas. Every Stage's canvas has them,
// so they run on the fit screen (no tool), the masks screen (the brush) and the reach screen (the walk test).

import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";

// A 48 x 32 room built through the masks Stage, which is done and empty.
function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio, stage: string): Promise<void> {
  await page.setViewportSize({ width: 1000, height: 560 }); // small enough that the room overflows once zoomed
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId(`stage-${stage}`).click();
  await expect(page.getByTestId("stage-title")).toHaveText(stage);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
}

interface View {
  zoom: number;
  left: number;
  top: number;
}

async function view(page: Page): Promise<View> {
  const canvas = page.getByTestId("canvas");
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  return { zoom: Number(await canvas.getAttribute("data-zoom")), left, top };
}

async function box(page: Page): Promise<{ x: number; y: number; width: number; height: number }> {
  return (await page.getByTestId("canvas").boundingBox())!;
}

// Where an image pixel's middle is on the page.
async function pixel(page: Page, x: number, y: number): Promise<{ x: number; y: number }> {
  const at = await box(page);
  const { zoom, left, top } = await view(page);
  return { x: at.x + left + (x + 0.5) * zoom, y: at.y + top + (y + 0.5) * zoom };
}

async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }, button: "left" | "middle" = "left"): Promise<void> {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down({ button });
  await page.mouse.move((from.x + to.x) / 2, (from.y + to.y) / 2);
  await page.mouse.move(to.x, to.y);
  await page.mouse.up({ button });
}

// Zoom in until the room overflows the canvas on both axes.
async function zoomIn(page: Page): Promise<void> {
  const canvas = page.getByTestId("canvas");
  for (let step = 0; step < 16 && Number(await canvas.getAttribute("data-zoom")) < 16; step++) await page.keyboard.press("z");
  await expect(canvas).toHaveAttribute("data-zoom", "16");
  await expect(canvas).toHaveAttribute("data-scroll-x", /.+/);
  await expect(canvas).toHaveAttribute("data-scroll-y", /.+/);
}

test("the wheel keeps the pixel under the pointer in place", async ({ page, studio }) => {
  builtRoom(studio);
  await open(page, studio, "fit");
  const at = await box(page);
  const pointer = { x: at.x + at.width * 0.3, y: at.y + at.height * 0.6 };
  await page.mouse.move(pointer.x, pointer.y);

  for (let step = 0; step < 3; step++) {
    const before = await view(page);
    const u = (pointer.x - at.x - before.left) / before.zoom;
    const v = (pointer.y - at.y - before.top) / before.zoom;
    await page.mouse.wheel(0, -100);
    await expect.poll(async () => (await view(page)).zoom).toBe(before.zoom + 1);
    const after = await view(page);
    expect(Math.abs(after.left + u * after.zoom - (pointer.x - at.x))).toBeLessThanOrEqual(after.zoom);
    expect(Math.abs(after.top + v * after.zoom - (pointer.y - at.y))).toBeLessThanOrEqual(after.zoom);
  }
});

test("a left drag pans where no tool is under it, and Home returns to the fit view", async ({ page, studio }) => {
  builtRoom(studio);
  await open(page, studio, "fit");
  const fitted = await view(page);
  await zoomIn(page);
  const zoomed = await view(page);

  const start = await pixel(page, 24, 16);
  await drag(page, start, { x: start.x - 60, y: start.y - 40 });

  const moved = await view(page);
  expect(moved.left).toBe(zoomed.left - 60);
  expect(moved.top).toBe(zoomed.top - 40);

  await page.keyboard.press("Home");
  expect(await view(page)).toEqual(fitted);
});

test("on the masks screen the brush paints and doesn't pan; Space and the middle button pan over it", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio, "masks");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-masks", /solid:0/);
  await page.keyboard.press("b");
  await zoomIn(page);
  const zoomed = await view(page);

  await drag(page, await pixel(page, 10, 8), await pixel(page, 20, 8));
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(await view(page)).toEqual(zoomed);

  const start = await pixel(page, 24, 16);
  await page.keyboard.down("Space");
  await drag(page, start, { x: start.x + 50, y: start.y + 30 });
  await page.keyboard.up("Space");
  const spaced = await view(page);
  expect(spaced.left).toBe(zoomed.left + 50);
  expect(spaced.top).toBe(zoomed.top + 30);

  const middle = await pixel(page, 24, 16);
  await drag(page, middle, { x: middle.x - 20, y: middle.y - 10 }, "middle");
  const panned = await view(page);
  expect(panned.left).toBe(spaced.left - 20);
  expect(panned.top).toBe(spaced.top - 10);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)"); // neither made a Decision
});

test("clicks and strokes land on the right pixel after zoom and pan", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio, "masks");
  await page.keyboard.press("b");
  await zoomIn(page);
  const zoomed = await view(page);
  await page.keyboard.press("Shift+ArrowLeft");
  await page.keyboard.press("ArrowDown");
  expect(await view(page)).not.toEqual(zoomed);

  await drag(page, await pixel(page, 30, 20), await pixel(page, 34, 20));

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { data: { points: number[][] } }[] }[];
  const points = stages.find((entry) => entry.stage === "masks")!.decisions[0].data.points;
  expect(points[0]).toEqual([30, 20]);
  expect(points.at(-1)).toEqual([34, 20]);
});

test("an arrow key pans the image; not in a text field", async ({ page, studio }) => {
  builtRoom(studio);
  await open(page, studio, "fit");
  await zoomIn(page);
  const start = await view(page);

  await page.keyboard.press("ArrowLeft"); // the view scrolls left, so the image moves right
  const once = await view(page);
  expect(once.left).toBeGreaterThan(start.left);
  expect(once.top).toBe(start.top);
  await page.keyboard.press("Shift+ArrowUp");
  const faster = await view(page);
  expect(faster.top - start.top).toBeGreaterThan(once.left - start.left);

  const field = page.locator("aside input[type=number], aside input[type=text]").first();
  await field.focus();
  await page.keyboard.press("ArrowLeft");
  expect(await view(page)).toEqual(faster);
});

test("the walk test keeps the arrow keys", async ({ page, studio }) => {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
  studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify({ decision: "flood", data: { x: 0, y: 0, mask: "solid" } }));
  studio.run(ROOM);
  const marker = { id: "spawn.main", type: "spawn", x: 36, y: 16 };
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "marker", data: marker }));
  studio.run(ROOM);
  await open(page, studio, "reach");
  await page.getByTestId("walk-toggle").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-body", "36,16");
  const before = await view(page);

  await page.keyboard.press("ArrowRight");

  await expect(page.getByTestId("canvas")).toHaveAttribute("data-body", "37,16");
  expect(await view(page)).toEqual(before);
});

test("scrollbars show on an overflowing axis only, and a thumb drags the image", async ({ page, studio }) => {
  builtRoom(studio);
  await open(page, studio, "fit");
  const canvas = page.getByTestId("canvas");
  const at = await box(page);

  for (let step = 0; step < 15; step++) {
    const { zoom } = await view(page);
    await expect.poll(async () => (await canvas.getAttribute("data-scroll-x")) !== null).toBe(48 * zoom > at.width);
    await expect.poll(async () => (await canvas.getAttribute("data-scroll-y")) !== null).toBe(32 * zoom > at.height);
    await page.keyboard.press("z");
    await expect(canvas).not.toHaveAttribute("data-zoom", String(zoom));
  }

  await page.keyboard.press("Home");
  await zoomIn(page);
  const [start, length, track] = (await canvas.getAttribute("data-scroll-x"))!.split(",").map(Number);
  expect(start).toBeGreaterThanOrEqual(0);
  expect(start + length).toBeLessThanOrEqual(track);
  const before = await view(page);

  await drag(page, { x: at.x + start + length / 2, y: at.y + at.height - 4 }, { x: at.x + start + length / 2 + 20, y: at.y + at.height - 4 });

  const after = await view(page);
  expect(after.left).toBeLessThan(before.left); // the thumb moved right, so the view moved right
  expect(after.top).toBe(before.top);
  const [moved] = (await canvas.getAttribute("data-scroll-x"))!.split(",").map(Number);
  expect(moved).toBeGreaterThan(start);

  const [yStart, yLength] = (await canvas.getAttribute("data-scroll-y"))!.split(",").map(Number);
  await drag(page, { x: at.x + at.width - 4, y: at.y + yStart + yLength / 2 }, { x: at.x + at.width - 4, y: at.y + yStart + yLength / 2 + 15 });
  expect((await view(page)).top).toBeLessThan(before.top);
});

test("panning far past an edge leaves part of the image on the canvas", async ({ page, studio }) => {
  builtRoom(studio);
  await open(page, studio, "fit");
  await zoomIn(page);
  const at = await box(page);

  for (const key of ["Shift+ArrowRight", "Shift+ArrowDown"]) for (let step = 0; step < 12; step++) await page.keyboard.press(key);
  let now = await view(page);
  expect(now.left + 48 * now.zoom).toBeGreaterThan(0);
  expect(now.top + 32 * now.zoom).toBeGreaterThan(0);

  for (const key of ["Shift+ArrowLeft", "Shift+ArrowUp"]) for (let step = 0; step < 24; step++) await page.keyboard.press(key);
  now = await view(page);
  expect(now.left).toBeLessThan(at.width);
  expect(now.top).toBeLessThan(at.height);
});

test("every Stage's canvas screen says how to pan", async ({ page, studio }) => {
  builtRoom(studio);
  await open(page, studio, "fit");
  await expect(page.getByTestId("canvas-hint")).toContainText("Space");
  await expect(page.getByTestId("canvas-hint")).toContainText("arrow keys");
});
