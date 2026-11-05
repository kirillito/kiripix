// The flows of ticket 0054 (spec §6.1, §11): a y-sort line for a Layer, the "always above" flag, and the Layers drawn over or
// under the Body in the walk test, against a real `kiripix serve` on a temporary Project. The sort positions are `place`'s own.

import type { Page } from "@playwright/test";
import { expect, layeredRoom, test, type Studio } from "./harness";

const ROOM = "room.alley";

async function open(page: Page, studio: Studio, stageName: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId(`stage-${stageName}`).click();
  await expect(page.getByTestId("stage-title")).toHaveText(stageName);
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

interface Journal {
  name: string;
  data: Record<string, unknown>;
}

function placeStage(studio: Studio): { decisions: Journal[]; sort: Record<string, unknown>[] } {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: Journal[]; sort: Record<string, unknown>[] }[];
  return stages.find((entry) => entry.stage === "place")!;
}

function place(studio: Studio, id: string, type: string, x: number, y: number): void {
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "marker", data: { id, type, x, y } }));
}

async function over(page: Page): Promise<string[]> {
  return ((await page.getByTestId("canvas").getAttribute("data-layers-over")) ?? "").split(" ").filter(Boolean).sort();
}

test("drawing a line for a Layer is one Decision naming it, the toggle is one, and a Layer is shown while its line is drawn", async ({
  page,
  studio,
}) => {
  layeredRoom(studio);
  await open(page, studio, "place");
  const canvas = page.getByTestId("canvas");
  await expect(page.getByTestId("sort-layers")).toBeVisible();

  await page.getByTestId("sort-layer-crate").click();
  await expect(page.getByTestId("marker-type")).toHaveValue("ysort");
  await expect(canvas).toHaveAttribute("data-layer-shown", "crate");
  await dragPixel(page, [18, 14], [30, 14]);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(placeStage(studio).decisions).toHaveLength(1);
  expect(placeStage(studio).decisions[0]).toMatchObject({
    name: "marker",
    data: { id: "ysort.1", type: "ysort", x: 18, y: 14, x2: 30, y2: 14, layer: "crate" },
  });
  await expect(page.getByTestId("sort-crate")).toHaveText("sorts at y 14");
  expect(placeStage(studio).sort).toEqual([{ layer: "crate", above: false, marker: "ysort.1", y: 14, slope: 0 }]);

  await page.getByTestId("above-lamp").click(); // controlled: it changes once the Decision is made

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(placeStage(studio).decisions[1]).toMatchObject({ name: "above", data: { layer: "lamp", above: true } });
  await expect(page.getByTestId("sort-lamp")).toHaveText("always above the Body");

  await expect(page.getByTestId("above-lamp")).toBeChecked();
  await page.getByTestId("above-lamp").click();
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  expect(placeStage(studio).decisions[2]).toMatchObject({ name: "above", data: { layer: "lamp", above: false } });
});

test("a layer.no_ysort finding jumps to its Layer on the place screen", async ({ page, studio }) => {
  layeredRoom(studio);
  await open(page, studio, "place");

  await page.getByTestId("checks").getByText("layer.no_ysort").first().click();

  await expect(page.getByTestId("marker-type")).toHaveValue("ysort");
  await expect(page.getByTestId("marker-layer")).toHaveValue(/^(crate|lamp)$/);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-layer-shown", /^(crate|lamp)$/);
});

test("in the walk test, a Layer is over the Body north of its line, under it south of it, and an always-above Layer is over in both", async ({
  page,
  studio,
}) => {
  layeredRoom(studio);
  studio.kiripix(
    "decide", ROOM, "place", "--decision",
    JSON.stringify({ decision: "marker", data: { id: "ysort.1", type: "ysort", x: 18, y: 14, x2: 30, y2: 14, layer: "crate" } }),
  );
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "above", data: { layer: "lamp", above: true } }));
  place(studio, "spawn.main", "spawn", 24, 20);
  studio.run(ROOM);
  await open(page, studio, "reach");

  await page.getByTestId("walk-toggle").click();
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-body", "24,20");
  await expect.poll(() => over(page)).toEqual(["lamp"]); // south of the line: the Body is in front of crate

  for (let step = 0; step < 6; step++) await page.keyboard.press("ArrowUp");
  await expect(canvas).toHaveAttribute("data-body", "24,14");
  await expect.poll(() => over(page)).toEqual(["lamp"]); // on the line, the Body is still in front

  await page.keyboard.press("ArrowUp");
  await expect(canvas).toHaveAttribute("data-body", "24,13");
  await expect.poll(() => over(page)).toEqual(["crate", "lamp"]); // north of it: crate is over the Body

  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect.poll(() => over(page)).toEqual(["lamp"]);
});
