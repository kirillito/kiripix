// Ticket 0132 (ADR 0009, spec §11): the looks screen, against a real `kiripix serve`. An edit is imported and picked for a Look,
// a region is drawn on the Plate, and the room/Look toggle shows the edit inside the region only. Every action is one Command.

import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, layeredRoom, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const GREEN: [number, number, number, number] = [0, 228, 54, 255];
const ORANGE: [number, number, number, number] = [255, 163, 0, 255];
const WHITE: [number, number, number, number] = [255, 255, 255, 255];
const GROUND = (x: number): [number, number, number, number] => (Math.floor(x / 2) < 24 ? [255, 0, 77, 255] : [29, 43, 83, 255]);

// The `layeredRoom`'s source (96 x 64: a crate at x 40 to 55, y 20 to 35 and a lamp at x 60 to 71, y 8 to 19), with the lamp
// green, and the crate orange too when `crate` is set: a redraw that the region doesn't cover.
function edit(crate: boolean): Buffer {
  const inCrate = (x: number, y: number) => x >= 40 && x < 56 && y >= 20 && y < 36;
  const inLamp = (x: number, y: number) => x >= 60 && x < 72 && y >= 8 && y < 20;
  return png(96, 64, (x, y) => (inLamp(x, y) ? GREEN : inCrate(x, y) ? (crate ? ORANGE : WHITE) : GROUND(x)));
}

function room(studio: Studio): void {
  layeredRoom(studio);
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-looks").click();
  await expect(page.getByTestId("stage-title")).toHaveText("looks");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("look-panel")).toBeVisible();
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

// The colour the canvas shows at a target pixel, at its centre. The overlay is switched off first, so it is the picture's own.
async function colourAt(page: Page, x: number, y: number): Promise<string> {
  const canvas = page.getByTestId("canvas");
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  return canvas.evaluate(
    (element: HTMLCanvasElement, at: number[]) => {
      const [px, py] = at;
      return Array.from(element.getContext("2d")!.getImageData(px, py, 1, 1).data).join(",");
    },
    [left + Math.floor((x + 0.5) * zoom), top + Math.floor((y + 0.5) * zoom)],
  );
}

function journal(studio: Studio): { name: string; data: Record<string, unknown> }[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "looks")!.decisions;
}

async function importEdit(page: Page, studio: Studio, look: string, crate: boolean): Promise<void> {
  await page.getByTestId("look-new").fill(look);
  const path = studio.write(`${look}.png`, edit(crate));
  await page.getByTestId("look-import-input").setInputFiles(path);
  await expect(page.getByTestId(`look-${look}`)).toBeVisible();
}

test("an edit is imported for a named Look, a region is drawn, and the toggle changes only the region", async ({ page, studio }) => {
  room(studio);
  await open(page, studio);
  await page.getByTestId("look-opacity").fill("0"); // the tint would hide the picture's own colours

  await importEdit(page, studio, "lamp_off", false);
  await expect(page.getByTestId("look-lamp_off")).toContainText("lamp_off");
  expect(journal(studio).map((entry) => entry.name)).toEqual(["pick"]);
  expect(journal(studio)[0].data).toMatchObject({ look: "lamp_off" });
  await expect(page.getByTestId("look-list")).toContainText("no region");

  await page.keyboard.press("g");
  for (const [x, y] of [[28, 2], [38, 2], [38, 12], [28, 12]]) await clickPixel(page, x, y);
  await page.keyboard.press("Enter");

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(journal(studio)[1]).toMatchObject({ name: "polygon", data: { look: "lamp_off", points: [[28, 2], [38, 2], [38, 12], [28, 12]] } });
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-look-pieces", /[12]/);

  await page.getByTestId("view-room").click();
  const roomLamp = await colourAt(page, 32, 6);
  const roomRest = [await colourAt(page, 5, 5), await colourAt(page, 42, 22), await colourAt(page, 40, 2)];
  await page.getByTestId("view-look").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-look-view", "look");
  const lookLamp = await colourAt(page, 32, 6);
  const lookRest = [await colourAt(page, 5, 5), await colourAt(page, 42, 22), await colourAt(page, 40, 2)];

  expect(lookLamp).not.toBe(roomLamp);
  expect(lookLamp).toBe("0,228,54,255");
  expect(roomLamp).toBe("255,163,0,255");
  expect(lookRest).toEqual(roomRest);

  await page.keyboard.press("v");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-look-view", "room");
  expect(await colourAt(page, 32, 6)).toBe(roomLamp);
});

test("a Condition is one `look` Decision, and a brush stroke is one `brush` Decision", async ({ page, studio }) => {
  room(studio);
  await open(page, studio);
  await importEdit(page, studio, "lamp_off", false);

  await page.getByTestId("look-condition").fill("circuit.hall:off");
  await page.getByTestId("look-condition-set").click();
  await expect(page.getByTestId("look-lamp_off")).toContainText("when circuit.hall:off");
  expect(journal(studio).at(-1)).toMatchObject({ name: "look", data: { look: "lamp_off", condition: "circuit.hall:off" } });

  await page.keyboard.press("b");
  await dragPixel(page, [30, 5], [36, 5]);
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  expect(journal(studio)).toHaveLength(3);
  expect(journal(studio)[2]).toMatchObject({ name: "brush", data: { look: "lamp_off", erase: false } });

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
});

test("a difference box is previewed, then recorded as one Decision", async ({ page, studio }) => {
  room(studio);
  await open(page, studio);
  await importEdit(page, studio, "lamp_off", false);

  await page.keyboard.press("d");
  await dragPixel(page, [26, 1], [40, 13]);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-staged", "26,1,40,13");
  expect(journal(studio)).toHaveLength(1); // a drag only stages it
  await page.getByTestId("look-tolerance").fill("3");
  await page.getByTestId("difference-record").click();

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(journal(studio)[1]).toMatchObject({ name: "difference", data: { look: "lamp_off", x0: 26, y0: 1, x1: 40, y1: 13, tolerance: 3 } });
  await expect(page.getByTestId("look-list")).toContainText(/\d+ px change/);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-staged", "");
});

test("a drift finding's box is drawn on the canvas, and clicking the finding goes to it", async ({ page, studio }) => {
  room(studio);
  await open(page, studio);
  await importEdit(page, studio, "lamp_off", true); // the crate is redrawn as well, outside the region
  await page.keyboard.press("g");
  for (const [x, y] of [[28, 2], [38, 2], [38, 12], [28, 12]]) await clickPixel(page, x, y);
  await page.keyboard.press("Enter");

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await expect(page.getByTestId("look-list")).toContainText(/\d+ px change/); // the region is built
  const finding = page.getByTestId("finding-look.drift");
  await expect(finding).toBeVisible();
  const drawn = await page.getByTestId("canvas").getAttribute("data-drift");
  expect(drawn).toMatch(/^\d+,\d+,\d+,\d+/);
  const [x, y, width, height] = drawn!.split(" ")[0].split(",").map(Number);
  expect(x).toBeLessThanOrEqual(24);
  expect(x + width).toBeGreaterThan(20);
  expect(y + height).toBeGreaterThan(10);

  await finding.click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-focus", `${x + Math.floor(width / 2)},${y + Math.floor(height / 2)}`);
  await expect(page.getByTestId("drift-hint")).toBeVisible();
});

test("the Look's solid is painted as one `solid` Decision, and the Look has its own solid.png", async ({ page, studio }) => {
  room(studio);
  await open(page, studio);
  await importEdit(page, studio, "lamp_off", false);
  await page.keyboard.press("s");
  await page.keyboard.press("b");
  await dragPixel(page, [10, 20], [20, 20]);

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(journal(studio)[1]).toMatchObject({ name: "solid", data: { look: "lamp_off", erase: false } });
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-masks", /solid:[1-9]/);
  mkdirSync(join(studio.cwd), { recursive: true });
  const built = JSON.parse(readFileSync(join(studio.cwd, "assets", "room", "alley", "work", "looks", "looks.json"), "utf-8")) as { looks: { solid: string | null }[] };
  expect(built.looks[0].solid).toBe("lamp_off/solid.png");
});
