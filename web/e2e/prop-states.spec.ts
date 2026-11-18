// The flows of ticket 0261 (spec §6.2, §11): a Prop's states, against a real `kiripix serve` on a temporary Project. The
// UI holds no logic: every action here is one Command, and the checks read what the Commands recorded.

import type { Page } from "@playwright/test";
import { expect, png, test, type Studio } from "./harness";

const PROP = "prop.bin";
const GREEN: [number, number, number, number] = [0, 255, 0, 255];
const RED: [number, number, number, number] = [255, 0, 77, 255];

// A 32 x 32 Source (16 x 16 at scale 2): a red block on the chroma green.
function standing(): Buffer {
  return png(32, 32, (x, y) => (x >= 6 && x < 26 && y >= 8 && y < 28 ? RED : GREEN));
}

// A 24 x 12 Source (12 x 6 at scale 2): the bin lying down.
function toppled(): Buffer {
  return png(24, 12, (x, y) => (x >= 2 && x < 22 && y >= 2 && y < 10 ? RED : GREEN));
}

function declare(studio: Studio): void {
  const data = { id: "toppled", width: 12, height: 6 };
  studio.kiripix("decide", PROP, "source", "--decision", JSON.stringify({ decision: "state", data }));
}

// A Prop with two states, built to the footprint, which waits for the Owner.
function twoStates(studio: Studio): void {
  studio.kiripix("new", "prop", "bin");
  studio.kiripix("set", PROP, "brief", "width=16", "height=16");
  studio.kiripix("set", PROP, "fit", "scale=2");
  studio.kiripix("pick", PROP, studio.importVariant(PROP, "standing.png", standing()));
  declare(studio);
  studio.write("toppled.png", toppled());
  const variant = studio.json("import", PROP, "incoming/toppled.png", "--state", "toppled").data.variant as string;
  studio.kiripix("pick", PROP, variant, "--state", "toppled");
  studio.run(PROP);
}

async function open(page: Page, studio: Studio, stageName: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${PROP}`).click();
  await page.getByTestId(`stage-${stageName}`).click();
}

async function pixel(page: Page, x: number, y: number): Promise<{ x: number; y: number }> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  return { x: box.x + left + (x + 0.5) * zoom, y: box.y + top + (y + 0.5) * zoom };
}

function footprints(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", PROP).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "footprint")!.decisions.map((decision) => decision.data);
}

test("selecting the second state and drawing a footprint records a Decision naming it", async ({ page, studio }) => {
  twoStates(studio);
  await open(page, studio, "footprint");
  await expect(page.getByTestId("state-strip")).toBeVisible();
  await expect(page.getByTestId("state-default")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("state-toppled-pick")).toContainText("12x6");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "16x16");

  await page.getByTestId("state-toppled").click();

  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "12x6");
  const at = await pixel(page, 6, 5);
  await page.mouse.click(at.x, at.y);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(footprints(studio)).toEqual([{ polygon: [], origin: [6, 5], state: "toppled" }]);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-footprint-origin", "6,5");

  // Back on the default state the toppled origin isn't its own.
  await page.getByTestId("state-default").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "16x16");
  await expect(page.getByTestId("footprint-summary")).toContainText("Origin: not set");
  const home = await pixel(page, 8, 14);
  await page.mouse.click(home.x, home.y);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(footprints(studio).at(-1)).toEqual({ polygon: [], origin: [8, 14] });
  await page.screenshot({ path: "shots/prop-states-footprint.png" });
});

test("the side-by-side view shows both states at 1x, each at its origin on one ground line", async ({ page, studio }) => {
  twoStates(studio);
  const footprint = (data: Record<string, unknown>) =>
    studio.kiripix("decide", PROP, "footprint", "--decision", JSON.stringify({ decision: "footprint", data }));
  footprint({ polygon: [], origin: [8, 14] });
  footprint({ polygon: [], origin: [6, 5], state: "toppled" });
  studio.run(PROP);
  await open(page, studio, "footprint");

  await page.getByTestId("states-side-by-side").click();

  await expect(page.getByTestId("side-by-side")).toHaveAttribute("data-zoom", "1");
  const standingBox = (await page.getByTestId("side-img-default").boundingBox())!;
  const toppledBox = (await page.getByTestId("side-img-toppled").boundingBox())!;
  expect([standingBox.width, standingBox.height]).toEqual([16, 16]); // 1x: the same scale
  expect([toppledBox.width, toppledBox.height]).toEqual([12, 6]);
  await expect(page.getByTestId("side-default")).toHaveAttribute("data-origin", "8,14");
  await expect(page.getByTestId("side-toppled")).toHaveAttribute("data-origin", "6,5");
  // Each origin is on the one ground line.
  expect(standingBox.y + 14).toBeCloseTo(toppledBox.y + 5, 0);
  await page.screenshot({ path: "shots/prop-states-side-by-side.png" });
});

test("a state is declared, imported and picked from the strip, each as one Command", async ({ page, studio }) => {
  studio.kiripix("new", "prop", "bin");
  studio.kiripix("set", PROP, "brief", "width=16", "height=16");
  studio.kiripix("pick", PROP, studio.importVariant(PROP, "standing.png", standing()));
  await open(page, studio, "source");

  await page.getByTestId("state-id").fill("toppled");
  await page.getByTestId("state-width").fill("12");
  await page.getByTestId("state-height").fill("6");
  await page.getByTestId("state-declare").click();
  await expect(page.getByTestId("state-toppled")).toBeVisible();
  await expect(page.getByTestId("state-toppled")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("state-toppled-pick")).toContainText("no Source picked");

  await page.getByTestId("state-import-input").setInputFiles(studio.write("toppled.png", toppled()));
  const variant = page.locator('[data-testid^="variant-"]');
  await expect(variant).toHaveCount(1);
  await page.keyboard.press("1");
  await expect(variant).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("state-toppled-pick")).toContainText("Source ");

  const states = studio.json("show", PROP).data.states as { state: string; picked: string | null }[];
  expect(states.map((entry) => [entry.state, entry.picked !== null])).toEqual([["toppled", true]]);
});
