// Ticket 0346 (spec §11, masks screen): a named Mask of the Project is pickable, tinted, toggled and counted like `solid`, against
// a real `kiripix serve` on a temporary Project.

import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";

// A 48 x 32 room built to `place`, with `cover` added and painted over the left 16 columns, and an area with a cell of 32 over the
// left 32 columns: the cell is half covered by `cover`.
function coveredRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("masks-add", "cover", "--colour", "#00AA00", "--meaning", "half cover for a grid battle", "--view", "top");
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(16)));
  studio.run(ROOM);
  const polygon = { decision: "polygon", data: { mask: "cover", erase: false, points: [[0, 0], [15, 0], [15, 31], [0, 31]] } };
  studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify(polygon));
  const area = { decision: "marker", data: { id: "battle.yard", type: "area", x: 0, y: 0, x2: 31, y2: 31, cell: 32, walkable: false } };
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify(area));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-masks").click();
  await expect(page.getByTestId("stage-title")).toHaveText("masks");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("mask-cover")).toBeVisible();
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

function maskDecisions(studio: Studio): { name: string; data: Record<string, unknown> }[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "masks")!.decisions;
}

test("the picker lists the room view's painted Masks from describe, tinted, with their meaning", async ({ page, studio }) => {
  test.setTimeout(120_000);
  coveredRoom(studio);
  await open(page, studio);

  const rows = (studio.json("describe", "room").data.masks as { view: string; name: string; colour: string | null; derived: boolean }[]).filter(
    (row) => row.view === "top" && !row.derived,
  );
  const picker = page.getByRole("group", { name: "Mask" });
  await expect(picker.locator("button")).toHaveCount(rows.length);
  const cover = page.getByTestId("mask-cover");
  await expect(cover).toHaveAttribute("title", /half cover for a grid battle/);
  await expect(cover.locator(".swatch")).toHaveCSS("background-color", "rgb(0, 170, 0)");

  // The number keys pick in the order the Project lists them.
  const first = rows[0].name;
  const second = rows.findIndex((row) => row.name === "cover") + 1;
  await page.keyboard.press(String(second));
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-mask", "cover");
  await page.keyboard.press("1");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-mask", first);
});

test("a brush stroke on cover records one Decision on cover and leaves solid untouched; its overlay toggles; its half-covered cell shows", async ({ page, segmentingStudio: studio }) => {
  test.setTimeout(120_000);
  coveredRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");
  const before = maskDecisions(studio).length;

  await page.getByTestId("mask-cover").click();
  await expect(canvas).toHaveAttribute("data-mask", "cover");
  // The cell of the area is half covered by cover (the left 16 of its 32 columns).
  await expect(canvas).toHaveAttribute("data-half-cells", "0,0");
  await page.screenshot({ path: "test-results/masks-named-cover.png" });

  await page.keyboard.press("b");
  await dragPixel(page, [20, 8], [30, 8]);
  await expect(page.getByTestId("decision-count")).toHaveText(`${before + 1} Decision(s)`);
  const made = maskDecisions(studio);
  expect(made).toHaveLength(before + 1);
  expect(made.at(-1)!.name).toBe("brush");
  expect(made.at(-1)!.data).toMatchObject({ mask: "cover", erase: false });
  expect(made.filter((decision) => decision.data.mask === "solid")).toHaveLength(0);
  await expect(canvas).toHaveAttribute("data-masks", /solid:0/);

  // `cover` can be hidden with `solid` still showing.
  await page.getByTestId("mask-show-cover").uncheck();
  await expect(canvas).toHaveAttribute("data-hidden-masks", "cover");
  await page.getByTestId("mask-show-cover").check();
  await expect(canvas).toHaveAttribute("data-hidden-masks", "");
  expect(maskDecisions(studio)).toHaveLength(before + 1); // a toggle records nothing
});
