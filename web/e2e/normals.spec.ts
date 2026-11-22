// The flows of ticket 0343 (spec §11, ADR 0014): the room's normals screen, against a real `kiripix serve` on a temporary Project, with
// the fake depth Runner of tests/fixtures (a ramp, so the walkable floor is tilted) and no GPU.

import type { Page } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";
const FINDING = "finding-normals.not_flat_walkable";

// A 48 x 32 room whose left half is the wall, built through `masks`; the Stage `normals` is off.
function wallRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
  studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify({ decision: "flood", data: { x: 0, y: 0, mask: "solid" } }));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-normals").click();
  await expect(page.getByTestId("stage-title")).toHaveText("normals");
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

// The Owner's steps: `mode` to depth, run the Runner, accept its result.
async function build(page: Page): Promise<void> {
  await page.getByLabel("mode").selectOption("depth");
  await page.getByTestId("rerun").click();
  await page.getByTestId("accept").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-view", "lit");
}

interface Journal {
  name: string;
  data: Record<string, unknown>;
}

function decisions(studio: Studio): Journal[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: Journal[] }[];
  return stages.find((entry) => entry.stage === "normals")!.decisions;
}

test("switching mode to depth builds the Stage, a flatten stroke records one Decision, and the finding clears", async ({ page, segmentingStudio: studio }) => {
  wallRoom(studio);
  await open(page, studio);
  await expect(page.getByTestId("normals-off")).toBeVisible();
  await expect(page.getByTestId("tool-brush")).toBeDisabled();

  await build(page);
  await expect(page.getByTestId(FINDING).first()).toBeVisible();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-normal-boxes", /\d+,\d+,\d+,\d+/);
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");
  await page.screenshot({ path: "test-results/normals-lit.png" });

  await page.getByTestId("normals-radius").fill("12");
  await page.getByTestId("tool-brush").click();
  await dragPixel(page, [22, 16], [42, 16]);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  const made = decisions(studio);
  expect(made).toHaveLength(1);
  expect(made[0].name).toBe("flatten");
  expect(made[0].data).toMatchObject({ shape: "brush", radius: 12 });
  await expect(page.getByTestId(FINDING)).toHaveCount(0);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-normal-boxes", "");
  await page.screenshot({ path: "test-results/normals-flattened.png" });

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");
  await expect(page.getByTestId(FINDING).first()).toBeVisible();
});

test("the light follows the mouse, L shows the raw normals, and a finding jumps to its area", async ({ page, segmentingStudio: studio }) => {
  wallRoom(studio);
  await open(page, studio);
  await build(page);
  const canvas = page.getByTestId("canvas");

  const at = await pixel(page, 30, 10);
  await page.mouse.move(at.x - 3, at.y);
  await page.mouse.move(at.x, at.y);
  await expect(canvas).toHaveAttribute("data-light", "30,10");
  const lit = await canvas.getAttribute("data-lit-sample");
  const other = await pixel(page, 40, 10);
  await page.mouse.move(other.x, other.y);
  await expect(canvas).toHaveAttribute("data-light", "40,10");
  await expect(canvas).not.toHaveAttribute("data-lit-sample", lit!);
  expect(decisions(studio)).toHaveLength(0); // the light is a hover: nothing is recorded

  await page.keyboard.press("l");
  await expect(canvas).toHaveAttribute("data-view", "normals");
  await page.keyboard.press("l");
  await expect(canvas).toHaveAttribute("data-view", "lit");

  await expect(canvas).not.toHaveAttribute("data-focus", /.+/);
  await page.getByTestId(FINDING).first().click();
  await expect(canvas).toHaveAttribute("data-focus", /^\d+,\d+$/);
});

test("a flatten polygon with walkable on, and the Override brush, are one Decision each", async ({ page, segmentingStudio: studio }) => {
  wallRoom(studio);
  await open(page, studio);
  await build(page);
  const canvas = page.getByTestId("canvas");

  await page.getByTestId("normals-walkable").check();
  await page.keyboard.press("g");
  await expect(canvas).toHaveAttribute("data-tool", "polygon");
  for (const [x, y] of [[0, 0], [47, 0], [47, 31], [0, 31]]) {
    const at = await pixel(page, x, y);
    await page.mouse.click(at.x, at.y);
  }
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)[0]).toMatchObject({ name: "flatten", data: { shape: "polygon", walkable: true } });
  await expect(page.getByTestId(FINDING)).toHaveCount(0);

  await page.getByTestId("edit-override").click();
  await expect(page.getByTestId("tool-erase")).toHaveCount(0);
  await page.getByTestId("normal-left").click();
  await page.getByTestId("tool-brush").click();
  await page.getByTestId("normals-radius").fill("2");
  await dragPixel(page, [30, 10], [36, 10]);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(decisions(studio)[1].name).toBe("override");
  await expect(page.getByTestId(FINDING).first()).toBeVisible(); // the hand-painted tilt is a finding again
});
