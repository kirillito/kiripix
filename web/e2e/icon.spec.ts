// Ticket 0264 (spec §6.6, §11): an icon on the Prop's reused screens, with the square drawn on `fit`, against a real
// `kiripix serve` on a temporary Project.

import { join } from "node:path";
import { expect, png, test } from "./harness";

const ICON = "icon.potion";
const SHOTS = join(import.meta.dirname, "..", "test-results");
const GREEN: [number, number, number, number] = [0, 255, 0, 255];
const RED: [number, number, number, number] = [255, 0, 77, 255];

// A 64 x 64 Source: a red block on the flat chroma green; it is fitted onto a 16 px square with a padding of 2.
function potion(): Buffer {
  return png(64, 64, (x, y) => (x >= 12 && x < 52 && y >= 12 && y < 52 ? RED : GREEN));
}

test("an icon opens on the Prop's screens and draws its square on fit", async ({ page, studio }) => {
  studio.kiripix("new", "icon", "potion");
  studio.kiripix("set", ICON, "brief", "size=16", "padding=2");
  studio.kiripix("pick", ICON, studio.importVariant(ICON, "potion.png", potion()));
  studio.run(ICON);

  await page.goto(studio.home);
  // The status board lists it under its Kind: the Kind's heading, then its rows (a long list draws rows, not nested sections).
  const board = page.getByTestId("board");
  await expect(board.locator("h2", { hasText: /^icon$/ })).toBeVisible();
  await expect(board.getByTestId(`board-${ICON}`)).toBeVisible();
  await page.getByTestId(`asset-${ICON}`).click();

  // The reused screens, and no footprint: an icon has none.
  for (const name of ["source", "cutout", "fit", "palette", "finish"]) await expect(page.getByTestId(`stage-${name}`)).toBeVisible();
  await expect(page.getByTestId("stage-footprint")).toHaveCount(0);

  await page.getByTestId("stage-fit").click();
  await expect(page.getByTestId("stage-title")).toHaveText("fit");
  const square = page.getByTestId("icon-square");
  await expect(square).toBeVisible();
  await expect(square).toHaveAttribute("data-inset", "2");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "16x16");
  await page.screenshot({ path: join(SHOTS, "icon-fit.png") });

  // The other screens carry no square.
  await page.getByTestId("stage-palette").click();
  await expect(page.getByTestId("icon-square")).toHaveCount(0);
});
