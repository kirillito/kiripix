// Ticket 0187 (spec §11, Place): drawing an emitter's shape and direction and picking its colours, against a real
// `kiripix serve`. Every change is one `marker` Decision; `markers.json`, the built `place` output, has what was drawn.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";
const RED = "#FF004D"; // the left of the art, x < 24
const NAVY = "#1D2B53"; // the right of it

function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
  studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify({ decision: "flood", data: { x: 0, y: 0, mask: "solid" } }));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-place").click();
  await expect(page.getByTestId("stage-title")).toHaveText("place");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
}

async function pixel(page: Page, x: number, y: number): Promise<{ x: number; y: number }> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  return { x: box.x + left + (x + 0.5) * zoom, y: box.y + top + (y + 0.5) * zoom };
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

async function clickPixel(page: Page, x: number, y: number): Promise<void> {
  const at = await pixel(page, x, y);
  await page.mouse.click(at.x, at.y);
}

function decisions(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "place")!.decisions.map((decision) => decision.data);
}

function builtMarkers(studio: Studio): Record<string, unknown>[] {
  const found = (readdirSync(studio.cwd, { recursive: true }) as string[]).filter((name) => /(^|[\\/])place[\\/]markers.json$/.test(name));
  expect(found.length).toBeGreaterThan(0);
  return (JSON.parse(readFileSync(join(studio.cwd, found[0]), "utf-8")) as { markers: Record<string, unknown>[] }).markers;
}

test("a box emitter, a direction and two colours are drawn, built into markers.json, moved with their Marker and undone", async ({ page, studio }) => {
  test.setTimeout(180_000); // several `kiripix` calls while the UI is open
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");

  await page.getByTestId("marker-type").selectOption("emitter");
  await clickPixel(page, 30, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect(page.getByTestId("emitter-panel")).toBeVisible(); // the new emitter is selected

  // Shape: a box, then drawn on the room (the Marker is its top-left corner).
  await page.getByTestId("emitter-shape").selectOption("box");
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await dragPixel(page, [10, 4], [20, 12]);
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  await expect(canvas).toHaveAttribute("data-markers", "emitter.1@10,4");
  await expect(canvas).toHaveAttribute("data-emitters", "emitter.1:box:-:");

  // Direction: an arrow from the Marker, its length in px.
  await page.getByTestId("emitter-mode-direction").click();
  await dragPixel(page, [15, 8], [15, 0]);
  await expect(page.getByTestId("decision-count")).toHaveText("4 Decision(s)");
  await expect(page.getByTestId("emitter-direction")).toHaveText("Direction: 6 px, to (15, 0)");

  // Colours: the eyedropper on the room, and a swatch of the palette.
  await page.getByTestId("emitter-mode-eyedrop").click();
  await clickPixel(page, 2, 2);
  await expect(page.getByTestId("decision-count")).toHaveText("5 Decision(s)");
  await clickPixel(page, 40, 2);
  await expect(page.getByTestId("decision-count")).toHaveText("6 Decision(s)");
  await expect(page.getByTestId("emitter-colour-1")).toBeVisible();
  await clickPixel(page, 41, 3); // the same colour again: nothing is recorded
  await expect(page.getByTestId("emitter-hint")).toContainText("already in the list");
  await expect(page.getByTestId("decision-count")).toHaveText("6 Decision(s)");
  await page.screenshot({ path: "test-results/place-emitter.png" });

  expect(decisions(studio).at(-1)).toEqual({
    id: "emitter.1",
    type: "emitter",
    x: 10,
    y: 4,
    name: "emitter",
    shape: { type: "box", x2: 20, y2: 12 },
    direction: { x: 15, y: 0 },
    colours: [RED, NAVY],
  });
  studio.run(ROOM);
  const built = builtMarkers(studio).find((marker) => marker.id === "emitter.1");
  expect(built).toMatchObject({ shape: { type: "box", x2: 20, y2: 12 }, direction: { x: 15, y: 0 }, colours: [RED, NAVY] });

  // Moving the Marker moves its shape and its arrow, as one Decision.
  await page.getByTestId("emitter-mode-shape").click();
  await dragPixel(page, [16, 8], [20, 12]); // inside the box: it moves with its Marker and arrow
  await expect(page.getByTestId("decision-count")).toHaveText("7 Decision(s)");
  await expect(canvas).toHaveAttribute("data-emitters", `emitter.1:box:19,4:${RED}|${NAVY}`);
  expect(decisions(studio).at(-1)).toMatchObject({ x: 14, y: 8, shape: { type: "box", x2: 24, y2: 16 }, direction: { x: 19, y: 4 } });

  // `undo` restores the previous shape.
  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("6 Decision(s)");
  await expect(canvas).toHaveAttribute("data-emitters", `emitter.1:box:15,0:${RED}|${NAVY}`);
  await expect(canvas).toHaveAttribute("data-markers", "emitter.1@10,4");
});

test("an emitter's polygon is drawn by clicks, a colour is removed, and the direction is cleared", async ({ page, studio }) => {
  test.setTimeout(180_000);
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");

  await page.getByTestId("marker-type").selectOption("emitter");
  await clickPixel(page, 30, 16);
  await expect(page.getByTestId("emitter-panel")).toBeVisible();
  await page.getByTestId("emitter-shape").selectOption("polygon");
  await clickPixel(page, 24, 8);
  await clickPixel(page, 40, 8);
  await clickPixel(page, 32, 20);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)"); // nothing is recorded until it closes
  await clickPixel(page, 24, 8); // the first point closes it
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(decisions(studio).at(-1)).toMatchObject({ shape: { type: "polygon", points: [[24, 8], [40, 8], [32, 20]] } });
  await expect(canvas).toHaveAttribute("data-emitters", "emitter.1:polygon:-:");

  // A swatch adds a colour of the palette; remove takes it out.
  await page.getByTestId(`palette-${RED}`).click();
  await expect(canvas).toHaveAttribute("data-emitters", `emitter.1:polygon:-:${RED}`);
  await page.getByTestId("emitter-colour-remove-0").click();
  await expect(canvas).toHaveAttribute("data-emitters", "emitter.1:polygon:-:");

  await page.getByTestId("emitter-mode-direction").click();
  await dragPixel(page, [30, 12], [30, 4]);
  await expect(page.getByTestId("emitter-direction")).toContainText("Direction: 12 px");
  await page.getByTestId("emitter-direction-clear").click();
  await expect(page.getByTestId("emitter-direction")).toHaveText("No direction yet");
});
