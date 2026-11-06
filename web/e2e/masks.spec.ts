// The flows of ticket 0026 (spec §11): the masks screen, against a real `kiripix serve` on a temporary Project. SAM 2 is the
// fake Runner of tests/fixtures, as in the Python tests, so nothing is downloaded and no GPU is needed.

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, png, test, type Studio } from "./harness";

const ROOM = "room.alley";

// A 48 x 32 room built through the masks Stage, which is done and empty.
function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-masks").click();
  await expect(page.getByTestId("stage-title")).toHaveText("masks");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-masks", /solid:0/);
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

// How many pixels each Mask has set on the canvas, as the screen read them from the built Masks.
async function counts(page: Page): Promise<Record<string, number>> {
  const text = (await page.getByTestId("canvas").getAttribute("data-masks")) ?? "";
  return Object.fromEntries(text.split(" ").filter(Boolean).map((part) => {
    const [name, count] = part.split(":");
    return [name, Number(count)];
  }));
}

interface Journal {
  name: string;
  data: Record<string, unknown>;
}

function decisions(studio: Studio): Journal[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: Journal[] }[];
  return stages.find((entry) => entry.stage === "masks")!.decisions;
}

function assetFolder(studio: Studio): string {
  return join(studio.cwd, "assets", "room", "alley");
}

// Everything under decisions/ and the journal, with sizes and times: a write would change it.
function journalFiles(studio: Studio): string {
  const folder = assetFolder(studio);
  const walk = (directory: string): string[] =>
    readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? walk(path) : [`${path} ${statSync(path).size} ${statSync(path).mtimeMs}`];
    });
  return [...walk(join(folder, "decisions")), readFileSync(join(folder, "history.jsonl"), "utf-8")].join("\n");
}

test("a brush stroke records exactly one Decision, and Ctrl+Z removes it from the canvas", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.keyboard.press("b");

  await dragPixel(page, [10, 8], [30, 8]);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  const made = decisions(studio);
  expect(made).toHaveLength(1);
  expect(made[0].name).toBe("brush");
  expect(made[0].data).toMatchObject({ mask: "solid", erase: false });
  expect((made[0].data.points as number[][]).length).toBeGreaterThan(1);
  await expect.poll(async () => (await counts(page)).solid).toBeGreaterThan(20);

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");

  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");
  expect(decisions(studio)).toHaveLength(0);
  await expect.poll(async () => (await counts(page)).solid).toBe(0);

  await page.keyboard.press("Control+Shift+z");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect.poll(async () => (await counts(page)).solid).toBeGreaterThan(20);
});

test("a long stroke stamps each pixel of its path once, so a frame's cost doesn't grow with the stroke", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.keyboard.press("b");
  const canvas = page.getByTestId("canvas");
  const radius = Number(await canvas.getAttribute("data-radius"));

  const start = await pixel(page, 2, 8);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  for (let x = 3; x <= 45; x++) {
    const at = await pixel(page, x, 8);
    await page.mouse.move(at.x, at.y);
  }
  await expect(canvas).toHaveAttribute("data-stroke-stamps", String((2 * radius + 1) * 44));
  await page.mouse.up();

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect((decisions(studio)[0].data.points as number[][]).length).toBe(44);
});

test("hovering over an object previews its Mask and writes nothing to decisions/", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  const before = journalFiles(studio);
  await page.keyboard.press("c");
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-tool", "click");

  const at = await pixel(page, 30, 16);
  await page.mouse.move(at.x - 3, at.y);
  await page.mouse.move(at.x, at.y);

  await expect.poll(async () => Number(await canvas.getAttribute("data-preview"))).toBeGreaterThan(0);
  await page.waitForTimeout(300);
  expect(journalFiles(studio)).toBe(before);
  expect(decisions(studio)).toHaveLength(0);
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");

  await page.mouse.move(0, 0); // off the canvas: the preview goes
  await expect(canvas).toHaveAttribute("data-preview", "0");
});

test("a click segments, and shift-click subtracts, one Decision each", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.keyboard.press("c");

  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)[0]).toMatchObject({ name: "click", data: { x: 20, y: 16, mask: "solid", positive: true } });

  await page.keyboard.down("Shift");
  await clickPixel(page, 20, 16);
  await page.keyboard.up("Shift");
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(decisions(studio)[1]).toMatchObject({ name: "click", data: { x: 20, y: 16, mask: "solid", positive: false } });
});

async function previewCount(page: Page): Promise<number> {
  return Number(await page.getByTestId("canvas").getAttribute("data-preview"));
}

test("Shift-hover over two overlapping objects tints their overlap, and a Shift-click takes it away", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.keyboard.press("c");
  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect.poll(async () => (await counts(page)).solid).toBeGreaterThan(0);
  const before = (await counts(page)).solid;

  // The second object's segment, as a plain click would add it.
  const at = await pixel(page, 26, 16);
  await page.mouse.move(at.x - 3, at.y);
  await page.mouse.move(at.x, at.y);
  await expect.poll(() => previewCount(page)).toBeGreaterThan(0);
  const whole = await previewCount(page);

  await page.keyboard.down("Shift");
  await expect.poll(() => previewCount(page)).toBeLessThan(whole);
  await expect.poll(() => previewCount(page)).toBeGreaterThan(0);
  const overlap = await previewCount(page);
  expect(overlap).toBeGreaterThan(0);
  await page.mouse.click(at.x, at.y);
  await page.keyboard.up("Shift");

  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  const made = decisions(studio);
  expect(made.filter((entry) => entry.name === "click" && entry.data.positive === false)).toHaveLength(1);
  expect(made[1]).toMatchObject({ name: "click", data: { x: 26, y: 16, mask: "solid", positive: false } });
  await expect.poll(async () => (await counts(page)).solid).toBe(before - overlap);
});

test("Shift-hover over a part of the Mask that a flood made tints it, and over an empty part tints nothing", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.keyboard.press("f");
  await clickPixel(page, 5, 5); // the red left half of the Plate
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect.poll(async () => (await counts(page)).solid).toBeGreaterThan(100);

  await page.keyboard.press("c");
  await page.keyboard.down("Shift");
  const inside = await pixel(page, 12, 16);
  await page.mouse.move(inside.x - 3, inside.y);
  await page.mouse.move(inside.x, inside.y);
  await expect.poll(() => previewCount(page)).toBeGreaterThan(0);

  const empty = await pixel(page, 42, 16);
  await page.mouse.move(empty.x - 3, empty.y);
  await page.mouse.move(empty.x, empty.y);
  await expect.poll(() => previewCount(page)).toBe(0);
  await page.keyboard.up("Shift");
  expect(decisions(studio)).toHaveLength(1);
});

test("with rebuild off, a click waits for an explicit re-run of the Runner, then for Accept", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.getByLabel("Rebuild the Masks after each edit").uncheck();
  await page.keyboard.press("c"); // the checkbox still has the focus: the letters work all the same

  await clickPixel(page, 20, 16);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)[0].name).toBe("click");
  await expect(page.getByTestId("run")).toHaveCount(0);

  await page.getByTestId("rerun").click();

  await expect(page.getByTestId("accept")).toBeVisible();
  await expect(page.getByTestId("rerun")).toHaveCount(0);
  await expect(page.getByText("Lost the connection")).toHaveCount(0);
});

test("with a checkbox or the slider focused, letters and Ctrl+Z still work, and Space still toggles the checkbox", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");
  const rebuild = page.getByLabel("Rebuild the Masks after each edit");

  await rebuild.focus();
  await page.keyboard.press("f");
  await expect(canvas).toHaveAttribute("data-tool", "flood");
  await page.keyboard.press("Space");
  await expect(rebuild).not.toBeChecked();
  await page.keyboard.press("Space");
  await expect(rebuild).toBeChecked();

  await page.getByLabel("Overlay opacity").focus();
  await page.keyboard.press("b");
  await expect(canvas).toHaveAttribute("data-tool", "brush");

  await dragPixel(page, [10, 8], [30, 8]);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await rebuild.focus();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");

  await page.getByLabel("snap_cell").focus(); // typing into a number field stays typing
  await page.keyboard.press("f");
  await expect(canvas).toHaveAttribute("data-tool", "brush");
});

test("a brush stroke's rebuild can be cancelled, re-runs no Runner, and keeps the stroke's findings", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.route("**/decide", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    json.findings.push({ code: "test.kept", severity: "warning", message: "kept from the decide", owner_action: "Look." });
    await route.fulfill({ response, json });
  });
  await page.keyboard.press("b");

  const [run] = await Promise.all([page.waitForRequest("**/run"), dragPixel(page, [10, 8], [30, 8])]);

  expect(run.headers()["x-kiripix-job"]).toBeTruthy();
  expect(run.postDataJSON()).toMatchObject({ stage: "masks", rerun: false });
  await expect(page.getByText("kept from the decide")).toBeVisible();
});

test("flood fills a region in one Decision, and the other keys switch tools, Masks and the brush size", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await open(page, studio);
  const canvas = page.getByTestId("canvas");

  await page.keyboard.press("p");
  await expect(canvas).toHaveAttribute("data-mask", "pit");
  await page.keyboard.press("f");
  await expect(canvas).toHaveAttribute("data-tool", "flood");
  await clickPixel(page, 2, 2);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)[0]).toMatchObject({ name: "flood", data: { x: 2, y: 2, mask: "pit" } });
  await expect.poll(async () => (await counts(page)).pit).toBe(24 * 32); // the left half of the art is one colour

  await page.keyboard.press("e");
  await expect(canvas).toHaveAttribute("data-tool", "erase");
  const radius = Number(await canvas.getAttribute("data-radius"));
  await page.keyboard.press("]");
  await expect(canvas).toHaveAttribute("data-radius", String(radius + 1));
  await page.keyboard.press("[");
  await page.keyboard.press("[");
  await expect(canvas).toHaveAttribute("data-radius", String(radius - 1));

  await dragPixel(page, [2, 2], [2, 10]);
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(decisions(studio)[1]).toMatchObject({ name: "brush", data: { mask: "pit", erase: true } });
  await expect.poll(async () => (await counts(page)).pit).toBeLessThan(24 * 32);
});

test("dropping a painted Mask image imports it in one Decision, and the opacity control dims the overlay", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await open(page, studio);
  const painted = png(48, 32, (x, y) => (x < 4 && y < 5 ? [255, 0, 0, 255] : [0, 0, 0, 0]));

  await page.getByTestId("canvas").evaluate(async (element, bytes) => {
    const data = new DataTransfer();
    data.items.add(new File([new Uint8Array(bytes)], "painted.png", { type: "image/png" }));
    element.parentElement!.dispatchEvent(new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true }));
  }, [...painted]);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)[0].name).toBe("import");
  await expect.poll(async () => (await counts(page)).solid).toBe(20);

  await page.getByTestId("mask-opacity").fill("20");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-opacity", "0.2");
});

test("the flood tolerance slider records its value in the flood's one Decision, and moving it records nothing", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await open(page, studio);
  const before = journalFiles(studio);
  await page.keyboard.press("f");
  const slider = page.getByTestId("mask-tolerance");
  await expect(slider).toHaveAttribute("max", "0.2"); // the range is describe's
  await expect(slider).toHaveValue("0.04");

  await slider.fill("0.1");
  await slider.fill("0.07");
  await expect(page.getByTestId("mask-tolerance-value")).toHaveText("0.070");
  await page.waitForTimeout(300);
  expect(journalFiles(studio)).toBe(before);
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");

  await clickPixel(page, 2, 2);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)).toHaveLength(1);
  expect(decisions(studio)[0]).toMatchObject({ name: "flood", data: { x: 2, y: 2, mask: "solid", tolerance: 0.07 } });

  await page.keyboard.press("b");
  await expect(slider).toHaveCount(0); // it belongs to the flood tool
});

test("a flood on a one-pixel region shows the finding, and clicking it jumps to the point", async ({
  page,
  segmentingStudio: studio,
}) => {
  studio.room();
  const odd = png(96, 64, (x, y) => (x >= 20 && x < 22 && y >= 10 && y < 12 ? [0, 228, 54, 255] : [255, 0, 77, 255]));
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", odd));
  studio.run(ROOM);
  await open(page, studio);
  await page.keyboard.press("f");
  await page.getByTestId("mask-tolerance").fill("0");

  await clickPixel(page, 10, 5);

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  const finding = page.getByTestId("finding-mask.flood_filled_almost_nothing").first();
  await expect(finding).toContainText("(10, 5)");
  await expect(page.getByTestId("canvas")).not.toHaveAttribute("data-focus", /.+/);
  await finding.click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-focus", "10,5");
});

test("Wall off edges records one border Decision with the chosen sides, the wall shows, and Ctrl+Z removes it", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await open(page, studio);
  await page.getByTestId("border-left").uncheck();

  await page.getByTestId("border-wall").click();

  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(decisions(studio)).toHaveLength(1);
  expect(decisions(studio)[0]).toMatchObject({
    name: "border",
    data: { mask: "solid", sides: ["top", "right", "bottom"] },
  });
  // Top and bottom 48 x 2 each, right 2 x 28 between them: the left side stays open.
  await expect.poll(async () => (await counts(page)).solid).toBe(2 * 48 * 2 + 2 * 28);
  await page.screenshot({ path: "test-results/masks-wall-off-edges.png" });

  await page.locator("h1").click();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("0 Decision(s)");
  expect(decisions(studio)).toHaveLength(0);
  await expect.poll(async () => (await counts(page)).solid).toBe(0);
});

test("masks.open_edge lists each open side, and clicking it jumps to that edge", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await open(page, studio);
  await page.getByTestId("border-left").uncheck();
  await page.getByTestId("border-right").uncheck();
  await page.getByTestId("border-wall").click();
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  const findings = page.getByTestId("finding-masks.open_edge");
  // The decide's answer and the Stage's Checks both list them: two sides open, so each shows once or twice.
  await expect(findings.filter({ hasText: /\(0, / }).first()).toBeVisible();
  await expect(findings.filter({ hasText: /\(47, / }).first()).toBeVisible();
  await expect(findings.filter({ hasText: /\((?!0,|47,)/ })).toHaveCount(0);
  const canvas = page.getByTestId("canvas");
  await expect(canvas).not.toHaveAttribute("data-focus", /.+/);
  await findings.filter({ hasText: /\(47, / }).first().click();
  await expect(canvas).toHaveAttribute("data-focus", /^47,\d+$/);
});

test("with the room walled off by the UI, the Body still stops at the room's edge in the walk test", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "marker", data: { id: "spawn.main", type: "spawn", x: 20, y: 16 } }));
  await open(page, studio);
  await page.getByTestId("border-wall").click();
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect.poll(async () => (await counts(page)).solid).toBe(48 * 32 - 44 * 28);
  studio.run(ROOM);

  await page.getByTestId("stage-reach").click();
  await page.getByTestId("walk-toggle").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-body", "20,16");
  await page.keyboard.down("ArrowLeft");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-body", "8,16"); // the 2-pixel wall: the footprint starts at x = 2
  await page.waitForTimeout(300);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-body", "8,16");
  await page.keyboard.up("ArrowLeft");
});
