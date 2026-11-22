// The flows of ticket 0335 (spec §11): an Asset's style beside its references, against a real `kiripix serve` on a temporary Project.
// Three small rooms (no figures: a sprite builds slowly) measured on `palette`: two 48 x 32 rooms painted at one pixel are the
// references, and a 96 x 64 room painted at 2x, so every colour run is even, is out of their range.

import type { Page } from "@playwright/test";
import { art, expect, png, test, type Studio } from "./harness";

const FINE_A = "room.fine_a";
const FINE_B = "room.fine_b";
const BIG = "room.big";

// A room whose Source is `source`, built to its `palette`: `scale` is the fit's, `size` the brief's.
function build(studio: Studio, name: string, size: [number, number], scale: number, source: Buffer): string {
  const id = `room.${name}`;
  studio.kiripix("new", "room", name, "--view", "top");
  studio.kiripix("set", id, "brief", `width=${size[0]}`, `height=${size[1]}`);
  studio.kiripix("set", id, "fit", `scale=${scale}`);
  studio.kiripix("pick", id, studio.importVariant(id, `${name}.png`, source));
  studio.run(id);
  return id;
}

// Two colours split at `edge` of 48 pixels: runs of `edge` and `48 - edge`, so an odd split has a run gcd of 1.
const oddly = (edge: number) => png(96, 64, (x) => (Math.floor(x / 2) < edge ? [255, 0, 77, 255] : [29, 43, 83, 255]));

function rooms(studio: Studio): void {
  build(studio, "fine_a", [48, 32], 2, oddly(23));
  build(studio, "fine_b", [48, 32], 2, oddly(25));
  build(studio, "big", [96, 64], 1, art(24));
}

async function open(page: Page, studio: Studio, id: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${id}`).click();
  await page.getByTestId("stage-palette").click();
  await expect(page.getByTestId("stage-title")).toHaveText("palette");
}

async function reference(page: Page, id: string): Promise<void> {
  await page.getByTestId(`asset-${id}`).click();
  await page.getByTestId("stage-palette").click();
  await page.getByTestId("style-add").click();
  await expect(page.getByTestId("style-remove")).toBeVisible();
}

test("two references give a third's bars, with the out-of-range measure marked and its finding shown", async ({ page, studio }) => {
  rooms(studio);
  await open(page, studio, BIG);
  await expect(page.getByTestId("style-panel")).toBeVisible();
  await expect(page.getByTestId("style-bar-outline_density")).toHaveCount(0); // a room has no outline to measure
  await expect(page.getByTestId("style-range-pixel_scale")).toHaveCount(0); // no reference yet
  await expect(page.getByTestId("style-findings")).toHaveCount(0);

  await reference(page, FINE_A);
  await reference(page, FINE_B);
  expect((studio.json("probe", "style", BIG).data.result as { references: unknown[] }).references).toHaveLength(2);

  await page.getByTestId(`asset-${BIG}`).click();
  await page.getByTestId("stage-palette").click();
  const bar = page.getByTestId("style-bar-pixel_scale");
  await expect(bar).toHaveAttribute("data-out", "true");
  await expect(page.getByTestId("style-out-pixel_scale")).toBeVisible();
  await expect(page.getByTestId("style-value-pixel_scale")).toHaveText("16x");
  await expect(page.getByTestId("style-range-pixel_scale")).toHaveAttribute("data-high", "1");
  await expect(page.getByTestId("style-finding-style.pixel_scale")).toBeVisible();
  await expect(page.getByTestId("checks").getByTestId("finding-style.pixel_scale")).toBeVisible();

  // The references beside it, at one whole-number zoom, the furthest named.
  const compare = page.getByTestId("style-compare");
  await expect(compare).toHaveAttribute("data-zoom", /^[1-8]$/);
  await expect(page.getByTestId(`style-figure-${BIG}`)).toBeVisible();
  await expect(page.getByTestId(`style-figure-${FINE_A}`).locator("img")).toBeVisible();
  await expect(page.getByTestId(`style-figure-${FINE_B}`).locator("img")).toBeVisible();
  await expect(compare).toContainText("(furthest)");
  await page.screenshot({ path: "test-results/style-scores.png" });

  // A reference is measured against the others only, and so has no finding of its own.
  await page.getByTestId(`asset-${FINE_A}`).click();
  await page.getByTestId("stage-palette").click();
  await expect(page.getByTestId("style-panel")).toHaveAttribute("data-reference", "true");
  await expect(page.getByTestId("style-bar-pixel_scale")).toHaveAttribute("data-out", "false");
  await expect(page.getByTestId("style-findings")).toHaveCount(0);
});

test("a finding opens the panel, the board marks the references, and Remove reference takes one out", async ({ page, studio }) => {
  rooms(studio);
  await open(page, studio, FINE_A);
  await page.getByTestId("style-add").click();
  await expect(page.getByTestId(`list-reference-${FINE_A}`)).toBeVisible();
  await reference(page, FINE_B);

  await page.getByTestId(`asset-${BIG}`).click();
  await page.getByTestId("stage-fit").click();
  await expect(page.getByTestId("style-panel")).toHaveCount(0); // only the measured Stage shows it
  await page.getByTestId("stage-palette").click();
  await expect(page.getByTestId("style-panel")).toHaveAttribute("data-focused", "false");
  await page.getByTestId("checks").getByTestId("finding-style.pixel_scale").click();
  await expect(page.getByTestId("style-panel")).toHaveAttribute("data-focused", "true");

  await page.getByTestId("home").click();
  await expect(page.getByTestId(`reference-${FINE_A}`)).toBeVisible();
  await expect(page.getByTestId(`reference-${FINE_B}`)).toBeVisible();
  await expect(page.getByTestId(`reference-${BIG}`)).toHaveCount(0);
  await page.screenshot({ path: "test-results/style-board.png" });

  await page.getByTestId(`asset-${FINE_B}`).click();
  await page.getByTestId("stage-palette").click();
  await page.getByTestId("style-remove").click();
  await expect(page.getByTestId("style-add")).toBeVisible();
  const kept = studio.json("probe", "style", BIG).data.result as { references: { asset: string }[] };
  expect(kept.references.map((entry) => entry.asset)).toEqual([FINE_A]);
});
