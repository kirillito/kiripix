// The flows of ticket 0027 (spec §6.1, §11): the place screen and the walk test, against a real `kiripix serve`.

import { readFileSync, writeFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { art, expect, layeredRoom, test, type Studio } from "./harness";

const ROOM = "room.alley";

// A 48 x 32 room whose left `edge` columns are one colour, flooded into `solid`, built down to `place`. With the 12 x 8
// Body, a footprint at (x, y) covers x - 6 to x + 5 and y - 4 to y + 3, so walkable starts at x = edge + 6.
function walledRoom(studio: Studio, edge: number): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(edge)));
  studio.run(ROOM); // a flood is made on the Plate
  decideMask(studio, "flood", { x: 0, y: 0, mask: "solid" });
  studio.run(ROOM);
}

function decideMask(studio: Studio, decision: string, data: object): void {
  studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify({ decision, data }));
}

function place(studio: Studio, id: string, type: string, x: number, y: number, room = ROOM): void {
  const data = { id, type, x, y };
  studio.kiripix("decide", room, "place", "--decision", JSON.stringify({ decision: "marker", data }));
}

async function open(page: Page, studio: Studio, stageName: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId(`stage-${stageName}`).click();
  await expect(page.getByTestId("stage-title")).toHaveText(stageName);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
}

// Where an image pixel's middle is on the page.
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

function markers(studio: Studio, room = ROOM): Record<string, unknown>[] {
  const stages = studio.json("show", room).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "place")!.decisions.map((decision) => decision.data);
}

test("placing a Spawn records one Decision, and dragging it records one more and moves it", async ({ page, studio }) => {
  walledRoom(studio, 8);
  await open(page, studio, "place");

  await page.getByTestId("marker-id").fill("spawn.main");
  await clickPixel(page, 30, 16);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-markers", "spawn.main@30,16");
  expect(markers(studio)).toEqual([{ id: "spawn.main", type: "spawn", x: 30, y: 16 }]);

  await dragPixel(page, [30, 16], [36, 20]);

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await expect(canvas).toHaveAttribute("data-markers", "spawn.main@36,20");
  expect(markers(studio).at(-1)).toEqual({ id: "spawn.main", type: "spawn", x: 36, y: 20 });
});

test("clicking a Marker selects it and records nothing, and Ctrl+Z undoes the last placing", async ({ page, studio }) => {
  walledRoom(studio, 8);
  await open(page, studio, "place");
  await clickPixel(page, 30, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  await clickPixel(page, 30, 16);

  await expect(page.getByTestId("marker-save")).toBeVisible();
  await expect(page.getByTestId("marker-id")).toHaveValue("spawn.1");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-markers", "");
});

test("saving a selected Marker after dragging it keeps it where it was dragged", async ({ page, studio }) => {
  walledRoom(studio, 8);
  await open(page, studio, "place");
  await clickPixel(page, 30, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await clickPixel(page, 30, 16);
  await expect(page.getByTestId("marker-save")).toBeVisible();

  await dragPixel(page, [30, 16], [36, 20]);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await page.getByTestId("marker-save").click();

  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  expect(markers(studio).at(-1)).toEqual({ id: "spawn.1", type: "spawn", x: 36, y: 20 });
});

test("an Exit's dropdowns offer the target rooms and their Exits, and a light has its fields", async ({ page, studio }) => {
  walledRoom(studio, 8);
  studio.kiripix("new", "room", "plaza", "--view", "top");
  const exit = { id: "exit.west", type: "exit", x: 5, y: 5, target_room: ROOM, target_exit: "exit.east" };
  studio.kiripix("decide", "room.plaza", "place", "--decision", JSON.stringify({ decision: "marker", data: exit }));
  await open(page, studio, "place");

  await page.getByTestId("marker-type").selectOption("exit");
  await page.getByTestId("marker-id").fill("exit.east");
  await page.getByTestId("marker-target-room").selectOption("room.plaza");
  await expect(page.locator("#marker-exits option")).toHaveAttribute("value", "exit.west");
  await page.getByTestId("marker-target-exit").fill("exit.west");
  await clickPixel(page, 30, 16);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(markers(studio)).toEqual([
    { id: "exit.east", type: "exit", x: 30, y: 16, target_room: "room.plaza", target_exit: "exit.west" },
  ]);

  await page.getByTestId("marker-type").selectOption("light");
  await page.getByTestId("marker-radius").fill("24");
  await page.getByTestId("marker-energy").fill("0.5");
  await clickPixel(page, 20, 8);

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(markers(studio).at(-1)).toEqual({
    id: "light.1", type: "light", x: 20, y: 8, colour: "#ffffff", radius: 24, energy: 0.5,
  });
});

test("a y-sort line is drawn with a drag, in one Decision that names its Layer", async ({ page, studio }) => {
  layeredRoom(studio);
  await open(page, studio, "place");
  await page.getByTestId("marker-type").selectOption("ysort");
  await page.getByTestId("marker-layer").selectOption("lamp");

  await dragPixel(page, [20, 10], [40, 12]);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(markers(studio)).toEqual([{ id: "ysort.1", type: "ysort", x: 20, y: 10, x2: 40, y2: 12, layer: "lamp" }]);
});

test("in the walk test, the Body stops at a solid edge", async ({ page, studio }) => {
  walledRoom(studio, 24);
  place(studio, "spawn.main", "spawn", 36, 16);
  studio.run(ROOM);
  await open(page, studio, "reach");

  await page.getByTestId("walk-toggle").click();
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-body", "36,16");
  await expect(canvas).toHaveAttribute("data-zoom", "1"); // the game's resolution

  await page.keyboard.down("ArrowLeft");
  await expect(canvas).toHaveAttribute("data-body", "30,16"); // walkable starts at x = 30: the footprint touches x = 24
  await page.waitForTimeout(300);
  await expect(canvas).toHaveAttribute("data-body", "30,16");
  await page.keyboard.up("ArrowLeft");

  await page.keyboard.press("ArrowRight");
  await expect(canvas).toHaveAttribute("data-body", "31,16");

  studio.kiripix("set", ROOM, "brief", "mood=rainy"); // an agent at work doesn't send the Body back to the Spawn
  await expect(page.getByTestId("stage-reach")).toHaveAttribute("data-status", "stale");
  await expect(canvas).toHaveAttribute("data-body", "31,16");
});

test("unreachable Markers from reach are highlighted", async ({ page, studio }) => {
  walledRoom(studio, 8);
  // A wall at x 26 to 30 leaves the spots x 14 to 20 on its left and x 37 to 42 on its right.
  decideMask(studio, "brush", { mask: "solid", erase: false, radius: 2, points: [[28, 0], [28, 31]] });
  place(studio, "spawn.main", "spawn", 16, 16);
  place(studio, "spawn.lost", "spawn", 40, 16);
  studio.run(ROOM);

  await open(page, studio, "reach");

  await expect(page.getByTestId("unreachable")).toContainText("spawn.lost");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-unreachable", "spawn.lost");
});

test("the Body's dash crosses a pit but not solid", async ({ page, studio }) => {
  const settings = `${studio.cwd}/kiripix.toml`;
  writeFileSync(settings, readFileSync(settings, "utf-8").replace("dash = 0", "dash = 8"));
  walledRoom(studio, 8);
  decideMask(studio, "brush", { mask: "pit", erase: false, radius: 2, points: [[28, 0], [28, 31]] });
  place(studio, "spawn.main", "spawn", 20, 16);
  studio.run(ROOM);
  await open(page, studio, "reach");
  await page.getByTestId("walk-toggle").click();
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-body", "20,16");

  await page.keyboard.press("ArrowRight");
  await expect(canvas).toHaveAttribute("data-body", "20,16"); // the footprint would touch the pit

  await page.keyboard.press("Shift+ArrowRight");
  await expect(canvas).toHaveAttribute("data-body", "37,16");
});
