// Ticket 0092 (spec §11): the layers screen says where a click goes and what became of it, and a Layer can be removed.
// SAM 2 is the fake Runner of tests/fixtures, as in layers.spec.ts.

import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";

function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-layers").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("layers-panel")).toBeVisible();
}

async function clickPixel(page: Page, x: number, y: number): Promise<void> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  await page.mouse.click(box.x + left + (x + 0.5) * zoom, box.y + top + (y + 0.5) * zoom);
}

function layersStage(studio: Studio): { decisions: { name: string }[]; outputs: string[] } {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string }[]; outputs: string[] }[];
  return stages.find((entry) => entry.stage === "layers")!;
}

test("a new Layer is in the list with no pixels, a click goes to it, and the lift shows its count and its new pixels", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");

  await page.getByTestId("layer-new").click();
  await expect(page.getByTestId("layer-layer1")).toBeVisible();
  await expect(page.getByTestId("layer-state-layer1")).toHaveText("no pixels yet");
  await expect(page.getByTestId("layer-target")).toContainText("layer1");
  await expect(canvas).toHaveAttribute("data-target", "layer1");

  await page.getByLabel("Re-run the Runner after each click").check();
  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("layer-state-layer1")).toHaveAttribute("data-state", "lifted");
  await expect(page.getByTestId("layer-state-layer1")).toHaveText(/^[1-9]\d* px$/);
  await expect(canvas).toHaveAttribute("data-layer-flash", /layer1:[1-9]/);
  await page.screenshot({ path: "test-results/layers-legible.png" });
});

test("a typed Layer ID is listed when it is committed", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layer-id").press("Enter");
  await expect(page.getByTestId("layer-state-lamp")).toHaveText("no pixels yet");
});

test("removing a Layer takes it out of the list and the canvas, and undo brings it back", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.getByLabel("Re-run the Runner after each click").check();
  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("layer-state-lamp")).toHaveAttribute("data-state", "lifted");
  await expect(canvas).toHaveAttribute("data-layers-shown", "lamp");
  await page.getByLabel("Re-run the Runner after each click").uncheck(); // the remove and its undo rebuild without it

  await page.getByTestId("layer-remove-lamp").click();
  await expect(page.getByTestId("layer-lamp")).toHaveCount(0);
  await expect(canvas).toHaveAttribute("data-layers-shown", "");
  await expect.poll(() => layersStage(studio).outputs.some((path) => path.endsWith("layer.lamp.png"))).toBe(false);
  expect(layersStage(studio).decisions.at(-1)?.name).toBe("remove");

  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("layer-lamp")).toBeVisible();
  await expect(canvas).toHaveAttribute("data-layers-shown", "lamp");
  await expect.poll(() => layersStage(studio).outputs.some((path) => path.endsWith("layer.lamp.png"))).toBe(true);
});
