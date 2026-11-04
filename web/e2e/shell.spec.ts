// The flows of ticket 0025 (spec §11), against a real `kiripix serve` on a temporary Project.

import { appendFileSync, writeFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { art, expect, png, test, type Studio } from "./harness";

const ROOM = "room.alley";

async function openRoom(page: Page, studio: Studio, stage?: string) {
  await page.goto(`${studio.home}`);
  await page.getByTestId(`asset-${ROOM}`).click();
  if (stage) await page.getByTestId(`stage-${stage}`).click();
}

function stage(page: Page, name: string) {
  return page.getByTestId(`stage-${name}`);
}

async function picked(page: Page, studio: Studio) {
  studio.room();
  await openRoom(page, studio, "source");
  await expect(page.getByTestId("stage-title")).toHaveText("source");
  await page.getByTestId("import-input").setInputFiles(studio.write("alley.png", art()));
  const variant = page.locator('[data-testid^="variant-"]');
  await expect(variant).toHaveCount(1);
  await variant.click();
  await expect(variant).toHaveAttribute("aria-pressed", "true");
}

test("import and pick a Variant, change fit.mode in the generated panel, and see the stage bar update", async ({
  page,
  studio,
}) => {
  await picked(page, studio);
  await expect(stage(page, "source")).toHaveAttribute("data-status", "todo");

  await stage(page, "fit").click();
  await page.getByTestId("run").click();
  await expect(stage(page, "fit")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");

  await page.getByTestId("param-mode").selectOption("downscale");

  await expect(stage(page, "fit")).toHaveAttribute("data-status", "stale");
  await expect(stage(page, "palette")).toHaveAttribute("data-status", "stale");
  await expect(stage(page, "brief")).toHaveAttribute("data-status", "done");
  expect(studio.json("show", ROOM).data.stages).toContainEqual(
    expect.objectContaining({ stage: "fit", params: expect.objectContaining({ mode: "downscale" }) }),
  );
});

test("a parameter changed from the CLI updates the open UI without a reload", async ({ page, studio }) => {
  await picked(page, studio);
  studio.run(ROOM);
  await stage(page, "fit").click();
  await expect(stage(page, "fit")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("param-mode")).toHaveValue("grid");
  let reloads = 0;
  page.on("framenavigated", () => reloads++);

  studio.kiripix("set", ROOM, "fit", "mode=downscale");

  await expect(page.getByTestId("param-mode")).toHaveValue("downscale");
  await expect(stage(page, "fit")).toHaveAttribute("data-status", "stale");
  expect(reloads).toBe(0);
});

test("a dropped PNG is imported as a Variant, and a number key picks it", async ({ page, studio }) => {
  studio.room();
  await openRoom(page, studio, "source");
  const bytes = art().toString("base64");

  await page.getByTestId("dropzone").evaluate((zone, base64) => {
    const data = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
    const transfer = new DataTransfer();
    transfer.items.add(new File([data], "dropped.png", { type: "image/png" }));
    zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
  }, bytes);

  const variant = page.locator('[data-testid^="variant-"]');
  await expect(variant).toHaveCount(1);
  await page.keyboard.press("1");
  await expect(variant).toHaveAttribute("aria-pressed", "true");
  await expect(stage(page, "source")).toHaveAttribute("data-status", "todo");
});

test("a file that isn't a PNG is refused with its finding, and nothing is imported", async ({ page, studio }) => {
  studio.room();
  await openRoom(page, studio, "source");

  await page.getByTestId("import-input").setInputFiles(studio.write("notes.png", Buffer.from("not an image")));

  await expect(page.getByTestId("notice")).toBeVisible();
  await expect(page.locator('[data-testid^="variant-"]')).toHaveCount(0);
});

test("an idle UI stops asking: a refresh's own Commands don't start another refresh", async ({ page, studio }) => {
  studio.room();
  await openRoom(page, studio);
  await expect(page.getByTestId("stage-title")).toHaveText("brief");
  await page.waitForTimeout(1_000); // whatever loading itself set off has settled
  let commands = 0;
  page.on("request", (request) => {
    if (request.method() === "POST") commands++;
  });

  await page.waitForTimeout(2_000);

  expect(commands).toBe(0);
});

test("an Asset opens on what it needs next, then stays there after a Run", async ({ page, studio }) => {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art()));
  await openRoom(page, studio);
  await expect(page.getByTestId("stage-title")).toHaveText("brief");

  await page.getByTestId("run").click();
  await expect(stage(page, "fit")).toHaveAttribute("data-status", "done");

  await expect(page.getByTestId("stage-title")).toHaveText("brief");
});

test("a refused parameter goes back to the value that stands, with its finding", async ({ page, studio }) => {
  studio.room();
  await openRoom(page, studio, "fit");
  await expect(page.getByTestId("param-scale")).toHaveValue("2");

  await page.getByTestId("param-scale").fill("1.5");
  await page.getByTestId("param-scale").press("Enter");

  await expect(page.getByTestId("finding-set.invalid_value")).toBeVisible();
  await expect(page.getByTestId("param-scale")).toHaveValue("2");
});

test("an Asset that can't be read shows why, not an empty screen", async ({ page, studio }) => {
  studio.room();
  appendFileSync(`${studio.cwd}/assets/room/alley/asset.toml`, "\n[stages.nothing]\nx = 1\n");

  await page.goto(`${studio.home}`);

  await expect(page.getByTestId("finding-config.unknown_key")).toBeVisible();
});

test("a change made while the event stream was down is picked up when it reconnects", async ({ page, studio }) => {
  studio.room();
  await page.route("**/api/events", (route) => route.abort()); // no "changed" can reach the page
  await openRoom(page, studio, "fit");
  await expect(page.getByTestId("param-mode")).toHaveValue("grid");

  studio.kiripix("set", ROOM, "fit", "mode=downscale");
  await page.waitForTimeout(1_000); // longer than the folder watch takes: had it been connected, it would have heard
  await expect(page.getByTestId("param-mode")).toHaveValue("grid");
  await page.unroute("**/api/events");

  await expect(page.getByTestId("param-mode")).toHaveValue("downscale");
});

test("an agent's rebuild reloads the image on the canvas", async ({ page, studio }) => {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art()));
  studio.run(ROOM);
  await openRoom(page, studio, "fit");
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-loaded", "48x32");
  const shown = await canvas.getAttribute("data-after");

  studio.kiripix("set", ROOM, "fit", "mode=downscale");
  studio.run(ROOM);

  await expect(canvas).not.toHaveAttribute("data-after", shown!);
});

test("the status board filters by needs me, stale and failing, and opens a Stage", async ({ page, studio }) => {
  studio.room();
  studio.kiripix("new", "room", "plaza", "--view", "top");
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art()));
  studio.run(ROOM);
  studio.kiripix("set", ROOM, "fit", "mode=downscale");

  await page.goto(studio.home);
  const board = page.getByTestId("board");
  await expect(board.getByTestId(`board-${ROOM}`)).toBeVisible();
  await expect(board.getByTestId("board-room.plaza")).toBeVisible();

  await page.getByTestId("filter-stale").click();
  await expect(board.getByTestId(`board-${ROOM}`)).toBeVisible();
  await expect(board.getByTestId("board-room.plaza")).toHaveCount(0);

  await page.getByTestId("filter-failing").click();
  await expect(board.getByText("No Asset matches this filter.")).toBeVisible();

  await page.getByTestId("filter-needs-me").click();
  await expect(board.getByTestId("board-room.plaza")).toBeVisible();

  await board.getByTestId("board-room.plaza").getByRole("button", { name: /^source/ }).click();
  await expect(page.getByTestId("stage-title")).toHaveText("source");
});

test("the canvas stays at integer zoom, and fit shows a before/after slider", async ({ page, studio }) => {
  await picked(page, studio);
  await stage(page, "fit").click();
  await page.getByTestId("run").click();
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-loaded", "48x32");

  await expect(canvas).toHaveAttribute("data-before", /source\.png/);
  await expect(canvas).toHaveAttribute("data-after", /fit\.png/);
  await expect(canvas).toHaveAttribute("data-split", "0.50");
  const box = (await canvas.boundingBox())!;
  const middle = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.move(middle.x, middle.y);
  await page.mouse.down();
  await page.mouse.move(middle.x + 40, middle.y);
  await page.mouse.up();
  await expect(canvas).not.toHaveAttribute("data-split", "0.50");

  const zoom = Number(await canvas.getAttribute("data-zoom"));
  expect(Number.isInteger(zoom) && zoom >= 1).toBe(true);
  await page.keyboard.press("z");
  await expect(canvas).toHaveAttribute("data-zoom", String(zoom >= 16 ? 1 : zoom + 1));
  await page.getByTestId("game-frame").check();
  await expect(canvas).toHaveAttribute("data-zoom", "1");

  await stage(page, "palette").click(); // the real resolution holds on every Stage
  await expect(canvas).toHaveAttribute("data-after", /palette\.png|plate\.png/);
  await expect(canvas).toHaveAttribute("data-zoom", "1");
});

test("clicking a finding jumps to its position", async ({ page, studio }) => {
  await picked(page, studio);
  await stage(page, "palette").click();
  await page.getByTestId("run").click();
  await expect(stage(page, "palette")).toHaveAttribute("data-status", "done");

  // A pixel off the palette in the built image: the Check reports where it is, and the watch refreshes the UI.
  const built = `${studio.cwd}/assets/room/alley/work/palette/palette.png`;
  writeFileSync(built, png(48, 32, (x, y) => (x === 7 && y === 5 ? [1, 2, 3, 255] : [255, 0, 77, 255])));

  const finding = page.getByTestId("finding-palette.off_palette");
  await expect(finding).toBeVisible();
  await finding.click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-focus", "7,5");
});

test("a needs-review Stage opens with a before/after, and Accept with the session token clears it", async ({
  page,
  studio,
}) => {
  studio.roomInReview();

  await openRoom(page, studio);

  await expect(page.getByTestId("stage-title")).toHaveText("fit");
  await expect(stage(page, "fit")).toHaveAttribute("data-status", "needs-review");
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-before", /source\.png/);
  await page.getByTestId("accept").click();
  await expect(stage(page, "fit")).not.toHaveAttribute("data-status", "needs-review");
});

test("Accept without the session token is refused with the owner-only finding", async ({ page, studio }) => {
  studio.roomInReview();

  await page.goto(studio.url);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("accept").click();

  await expect(page.getByTestId("notice")).toContainText("owner");
  await expect(stage(page, "fit")).toHaveAttribute("data-status", "needs-review");
});

test("a parameter-only Stage's panel comes from describe, with its Checks live", async ({ page, studio }) => {
  studio.room();
  await openRoom(page, studio, "brief");
  await expect(page.getByTestId("param-width")).toHaveValue("48");

  await page.getByTestId("param-width").fill("50");
  await page.getByTestId("param-width").press("Enter");
  await page.getByTestId("run").click();

  await expect(page.getByTestId("finding-brief.size_not_tiles")).toBeVisible();
  await page.getByTestId("param-width").fill("48");
  await page.getByTestId("param-width").press("Enter");
  await page.getByTestId("run").click();
  await expect(page.getByTestId("checks-clean")).toBeVisible();
});
