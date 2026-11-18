// Ticket 0268 (spec §6.1, §11): draw a Link on the place screen, and cross it in the walk test, against a real `kiripix serve`.

import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";
const SHOTS = join(import.meta.dirname, "..", "test-results");

// A 48 x 32 room whose left 8 columns are solid. With the 12 x 8 Body, walkable is x 14 to 42, y 4 to 28.
function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(8)));
  studio.run(ROOM);
  studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify({ decision: "flood", data: { x: 0, y: 0, mask: "solid" } }));
  studio.run(ROOM);
}

function decide(studio: Studio, name: string, data: object): void {
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: name, data }));
}

async function open(page: Page, studio: Studio, stageName: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId(`stage-${stageName}`).click();
  await expect(page.getByTestId("stage-title")).toHaveText(stageName);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
}

async function clickPixel(page: Page, x: number, y: number): Promise<void> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  await page.mouse.click(box.x + left + (x + 0.5) * zoom, box.y + top + (y + 0.5) * zoom);
}

function placed(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "place")!.decisions.filter((entry) => entry.name === "link").map((entry) => entry.data);
}

test("drawing a Link records one link Decision, and the walk test crosses it one way", async ({ page, studio }) => {
  builtRoom(studio);
  decide(studio, "marker", { id: "spawn.main", type: "spawn", x: 20, y: 16 });
  studio.run(ROOM);
  await open(page, studio, "place");

  await page.getByTestId("marker-type").selectOption("link");
  await page.getByTestId("marker-kind").fill("climb");
  await page.getByTestId("marker-two-way").uncheck();
  await clickPixel(page, 20, 16);
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-pending-link", "20,16");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)"); // the first click alone records nothing
  await clickPixel(page, 38, 16);

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(placed(studio)).toEqual([{ id: "link.1", from: [20, 16], to: [38, 16], kind: "climb", two_way: false }]);
  await expect(canvas).toHaveAttribute("data-links", "link.1:20,16>38,16:climb:one");
  await expect(page.getByTestId("markers-link")).toContainText("link.1");
  await page.screenshot({ path: join(SHOTS, "place-link.png") });

  studio.run(ROOM);
  await open(page, studio, "reach");
  await page.getByTestId("walk-toggle").click();
  await expect(canvas).toHaveAttribute("data-body", "20,16");
  await page.keyboard.press("c");
  await expect(canvas).toHaveAttribute("data-body", "38,16");
  await page.keyboard.press("c"); // one way: no way back
  await page.waitForTimeout(200);
  await expect(canvas).toHaveAttribute("data-body", "38,16");
  await page.screenshot({ path: join(SHOTS, "reach-link-walk.png") });
});

test("a two-way Link is crossed back, and a Link is edited in the Marker panel", async ({ page, studio }) => {
  builtRoom(studio);
  decide(studio, "marker", { id: "spawn.main", type: "spawn", x: 20, y: 16 });
  decide(studio, "link", { id: "link.hop", from: [20, 16], to: [38, 16], kind: "hop" });
  studio.run(ROOM);

  await open(page, studio, "place");
  await page.getByTestId("marker-link.hop").click();
  await expect(page.getByTestId("marker-kind")).toHaveValue("hop");
  await expect(page.getByTestId("marker-two-way")).toBeChecked();
  await page.getByTestId("marker-kind").fill("jump");
  await page.getByTestId("marker-two-way").uncheck();
  await page.getByTestId("marker-save").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-links", "link.hop:20,16>38,16:jump:one");
  expect(placed(studio).at(-1)).toEqual({ id: "link.hop", from: [20, 16], to: [38, 16], kind: "jump", two_way: false });

  await page.getByTestId("marker-two-way").check();
  await page.getByTestId("marker-save").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-links", "link.hop:20,16>38,16:jump:two");
  studio.run(ROOM);

  await open(page, studio, "reach");
  await page.getByTestId("walk-toggle").click();
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-body", "20,16");
  await page.keyboard.press("c");
  await expect(canvas).toHaveAttribute("data-body", "38,16");
  await page.keyboard.press("c");
  await expect(canvas).toHaveAttribute("data-body", "20,16");
});
