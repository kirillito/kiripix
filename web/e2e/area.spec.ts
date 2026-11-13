// Ticket 0139 (spec §11, Place): drawing an area, with a cell, on the place screen, against a real `kiripix serve`.

import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";

// A 48 x 32 room whose left 16 columns are `solid`, built down to `place`. A cell of 32 over x 0 to 31 is half covered.
function walledRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(16)));
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

function decisions(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "place")!.decisions.map((decision) => decision.data);
}

test("an area is drawn with a cell of 32, resized, undone, and its ambiguous cell is highlighted", async ({ page, studio }) => {
  test.setTimeout(120_000); // several `kiripix` calls while the UI is open
  walledRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");

  await page.getByTestId("marker-type").selectOption("area");
  await page.getByTestId("marker-id").fill("battle.yard");
  await page.getByTestId("marker-cell").fill("32");
  await dragPixel(page, [3, 4], [20, 18]);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)).toEqual([
    { id: "battle.yard", type: "area", x: 3, y: 4, x2: 20, y2: 18, cell: 32, walkable: false },
  ]);
  await expect(canvas).toHaveAttribute("data-markers", "battle.yard@0,0-31,31"); // snapped out to the cell

  // The cell is half covered by `solid`: once `place` is built the info finding names it, and the canvas highlights it.
  studio.run(ROOM);
  await expect(canvas).toHaveAttribute("data-ambiguous", "battle.yard@0,0");
  await page.getByTestId("checks-info").click();
  const finding = page.getByTestId("finding-area.ambiguous_cells");
  await expect(finding).toBeVisible();
  await page.screenshot({ path: "test-results/place-area-ambiguous-cell.png" });

  // Resize by the bottom-right handle: one more Decision with the same ID.
  await dragPixel(page, [31, 31], [44, 20]);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(decisions(studio).at(-1)).toMatchObject({ id: "battle.yard", type: "area", x: 0, y: 0, x2: 63, y2: 31, cell: 32 }); // snapped out to two cells (outside the room: an error finding, not a refusal)
  await expect(canvas).toHaveAttribute("data-markers", "battle.yard@0,0-63,31");

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect(canvas).toHaveAttribute("data-markers", "battle.yard@0,0-31,31");

  await finding.click(); // jumps to the first ambiguous cell, and records nothing
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
});

test("an area without a cell is moved by its corner and a click on it selects without a Decision", async ({ page, studio }) => {
  walledRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");

  await page.keyboard.press("a"); // the letter picks the area tool
  await expect(page.getByTestId("marker-type")).toHaveValue("area");
  await page.getByTestId("marker-walkable").check();
  await dragPixel(page, [24, 6], [40, 20]);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)).toEqual([{ id: "area.1", type: "area", x: 24, y: 6, x2: 40, y2: 20, walkable: true }]);

  await dragPixel(page, [24, 6], [26, 8]); // the top-left handle
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await expect(canvas).toHaveAttribute("data-markers", "area.1@26,8-40,20");

  await page.getByTestId("marker-area.1").click();
  await expect(page.getByTestId("marker-save")).toBeVisible();
  await dragPixel(page, [33, 14], [35, 15]); // inside a selected area: moves it
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  await expect(canvas).toHaveAttribute("data-markers", "area.1@28,9-42,21");
});
