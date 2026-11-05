// The flows of ticket 0056 (spec §6.2, §11): a prop's screens, from the Source to a done footprint, against a real
// `kiripix serve` on a temporary Project.

import type { Page } from "@playwright/test";
import { expect, png, test, type Studio } from "./harness";

const PROP = "prop.bench";
const GREEN: [number, number, number, number] = [0, 255, 0, 255];
const RED: [number, number, number, number] = [255, 0, 77, 255];

// A 32 x 32 Source: a red block on the flat chroma green. `scale=2` takes it to the brief's 16 x 16.
function bench(): Buffer {
  return png(32, 32, (x, y) => (x >= 6 && x < 26 && y >= 8 && y < 28 ? RED : GREEN));
}

function newProp(studio: Studio): void {
  studio.kiripix("new", "prop", "bench");
  studio.kiripix("set", PROP, "brief", "width=16", "height=16");
  studio.kiripix("set", PROP, "fit", "scale=2");
}

// A prop built down to the footprint, which waits for the Owner.
function builtProp(studio: Studio): void {
  newProp(studio);
  studio.kiripix("pick", PROP, studio.importVariant(PROP, "bench.png", bench()));
  studio.run(PROP);
}

function stage(page: Page, name: string) {
  return page.getByTestId(`stage-${name}`);
}

async function open(page: Page, studio: Studio, stageName?: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${PROP}`).click();
  if (stageName) await stage(page, stageName).click();
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

function footprints(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", PROP).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "footprint")!.decisions.map((decision) => decision.data);
}

test("a prop goes from import to a done footprint", async ({ page, studio }) => {
  newProp(studio);
  await open(page, studio, "source");
  await page.getByTestId("import-input").setInputFiles(studio.write("bench.png", bench()));
  const variant = page.locator('[data-testid^="variant-"]');
  await expect(variant).toHaveCount(1);
  await page.keyboard.press("1");
  await expect(variant).toHaveAttribute("aria-pressed", "true");

  // The shared screens: run the Stages up to the footprint, which waits for the Owner.
  await stage(page, "cutout").click();
  await page.getByTestId("run").click();
  await expect(stage(page, "finish")).toHaveAttribute("data-status", "done");
  await expect(stage(page, "footprint")).toHaveAttribute("data-status", "needs-input");

  await stage(page, "footprint").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "16x16");
  await expect(page.getByTestId("next-hint")).toContainText("Draw the footprint and the origin");
  await expect(page.getByTestId("footprint-polygon")).toBeDisabled();

  await clickPixel(page, 8, 14);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  await page.getByTestId("footprint-polygon").click();
  await clickPixel(page, 3, 12);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await page.getByTestId("run").click(); // one point is no polygon
  await expect(page.getByTestId("checks")).toContainText("prop.footprint_too_small");
  await clickPixel(page, 12, 12);
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
  await clickPixel(page, 12, 14);
  await expect(page.getByTestId("decision-count")).toHaveText("4 Decision(s)");

  await page.getByTestId("run").click();
  await expect(page.getByTestId("checks-clean")).toBeVisible();
  await expect(stage(page, "footprint")).toHaveAttribute("data-status", "done");
  expect(footprints(studio).at(-1)).toEqual({ polygon: [[3, 12], [12, 12], [12, 14]], origin: [8, 14] });
});

test("moving the origin records one Decision, and Ctrl+Z takes it back", async ({ page, studio }) => {
  builtProp(studio);
  studio.kiripix("decide", PROP, "footprint", "--decision", JSON.stringify({ decision: "footprint", data: { polygon: [], origin: [8, 14] } }));
  await open(page, studio, "footprint");
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-footprint-origin", "8,14");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  await dragPixel(page, [8, 14], [10, 12]);

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await expect(canvas).toHaveAttribute("data-footprint-origin", "10,12");
  expect(footprints(studio)).toEqual([
    { polygon: [], origin: [8, 14] },
    { polygon: [], origin: [10, 12] },
  ]);

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect(canvas).toHaveAttribute("data-footprint-origin", "8,14");
});

test("an origin outside the sprite shows its finding, and a point drags in one Decision", async ({ page, studio }) => {
  builtProp(studio);
  const data = { polygon: [[2, 12], [12, 12], [12, 15]], origin: [20, 3] };
  studio.kiripix("decide", PROP, "footprint", "--decision", JSON.stringify({ decision: "footprint", data }));
  studio.run(PROP);
  await open(page, studio, "footprint");
  await expect(page.getByTestId("checks")).toContainText("prop.origin_outside");

  await dragPixel(page, [2, 12], [4, 13]);

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-footprint", "4,13 12,12 12,15");
  expect(footprints(studio).at(-1)).toEqual({ polygon: [[4, 13], [12, 12], [12, 15]], origin: [20, 3] });
});

test("the cutout shows its chroma colour and the Source against the cut, and a chroma that keys nothing is reported", async ({
  page,
  studio,
}) => {
  builtProp(studio);
  await open(page, studio, "cutout");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "32x32");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-before", /source\.png/);
  await expect(page.getByTestId("param-chroma")).toHaveValue("#00FF00");

  await page.getByTestId("param-chroma").fill("#FF00FF");
  await page.getByTestId("param-chroma").press("Enter");
  await expect(stage(page, "cutout")).toHaveAttribute("data-status", "stale");
  await page.getByTestId("run").click();
  await expect(page.getByTestId("checks")).toContainText("cutout.chroma_keyed_nothing");
});

test("a matting cutout is re-run and accepted like a layer's", async ({ page, segmentingStudio: studio }) => {
  builtProp(studio);
  await open(page, studio, "cutout");

  await page.getByTestId("param-method").selectOption("matting");

  await expect(page.getByTestId("rerun")).toBeVisible();
  await page.getByTestId("rerun").click();
  await expect(stage(page, "cutout")).toHaveAttribute("data-status", /needs-review|done/);
  if ((await stage(page, "cutout").getAttribute("data-status")) === "needs-review") {
    await page.getByTestId("accept").click();
  }
  await expect(stage(page, "cutout")).toHaveAttribute("data-status", "done");
});
