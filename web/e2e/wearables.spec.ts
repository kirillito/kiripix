// Ticket 0295 (spec §6.3, §11): a body's Wearables on the status board, and the stack preview on the body's `sheet` screen, against a
// real `kiripix serve` on a temporary Project and the fake Blender of tests/fixtures. The fake renders flat frames, so the test
// writes the Wearables' atlases and depth frames itself (what a real render would have), to make the stacks differ.

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { crc32, deflateSync } from "node:zlib";
import type { Page } from "@playwright/test";
import { expect, png, test, type Studio } from "./harness";

const BODY = "character.zed";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");
const SHOTS = join(import.meta.dirname, "..", "test-results");
const HAIR = "wearable.hair";
const CAP = "wearable.cap";

// A 16 bit gray PNG from a value for each pixel.
function gray16(width: number, height: number, value: (x: number, y: number) => number): Buffer {
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type, "latin1"), data]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const check = Buffer.alloc(4);
    check.writeUInt32BE(crc32(body));
    return Buffer.concat([length, body, check]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([16, 0, 0, 0, 0], 8);
  const rows = Buffer.alloc((width * 2 + 1) * height);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) rows.writeUInt16BE(value(x, y), y * (width * 2 + 1) + 1 + x * 2);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function build(studio: Studio): void {
  studio.kiripix("new", "character", "zed");
  const variant = studio.json("import", BODY, join(CHARACTERS, "rigged.glb")).data.variant as string;
  studio.kiripix("pick", BODY, variant);
  studio.kiripix(
    "decide", BODY, "clips", "--decision",
    JSON.stringify({ decision: "clip", data: { name: "idle", source: "idle", start: 0, end: 2, fps: 12, loop: true } }),
  );
  studio.kiripix("set", BODY, "palette", "colors=4");
  for (const stage of ["model", "rig", "clips", "render", "palette", "finish", "sheet"]) studio.kiripix("run", BODY, stage);
  for (const [id, name, order] of [[HAIR, "hair", 10], [CAP, "cap", 20]] as const) {
    studio.kiripix("new", "wearable", name, "--body", BODY);
    const own = studio.json("import", id, join(CHARACTERS, "rigged.glb")).data.variant as string;
    studio.kiripix("pick", id, own);
    studio.kiripix("set", id, "palette", "colors=4");
    studio.kiripix("set", id, "sheet", `order=${order}`);
    for (const stage of ["model", "rig", "render", "palette", "finish", "sheet"]) studio.kiripix("run", id, stage);
  }
}

const folder = (studio: Studio, id: string, stage: string) => join(studio.cwd, "assets", ...id.split("."), "work", stage);

// The Wearables' sheets as a real render would make them: hair green and near, cap blue and a little farther (still nearer than the
// body), so that by order the cap hides the hair and by depth the hair shows.
function paint(studio: Studio): void {
  for (const [id, colour, depth] of [[HAIR, [0, 228, 54, 255], 10], [CAP, [41, 173, 255, 255], 50]] as const) {
    const sheet = JSON.parse(readFileSync(join(folder(studio, id, "sheet"), "sheet.json"), "utf-8")) as { atlas: { width: number; height: number } };
    const { width, height } = sheet.atlas;
    writeFileSync(join(folder(studio, id, "sheet"), "color.png"), png(width, height, () => [colour[0], colour[1], colour[2], colour[3]]));
    writeFileSync(join(folder(studio, id, "sheet"), "depth.png"), gray16(width, height, () => depth));
  }
}

// The cap's render depth: its right half is farther than the body, so by depth the body shows there and by order the cap hides it.
function farRight(studio: Studio): { width: number; height: number } {
  const dir = folder(studio, CAP, "render");
  const document = JSON.parse(readFileSync(join(dir, "render.json"), "utf-8")) as {
    frame: { width: number; height: number };
    clips: { directions: Record<string, { files: { color: string; depth: string } }[]> }[];
  };
  const { width, height } = document.frame;
  for (const clip of document.clips) {
    for (const frames of Object.values(clip.directions)) {
      for (const frame of frames) {
        writeFileSync(join(dir, frame.files.color), png(width, height, () => [41, 173, 255, 255]));
        writeFileSync(join(dir, frame.files.depth), gray16(width, height, (x) => (x >= width / 2 ? 200 : 10)));
      }
    }
  }
  return { width, height };
}

async function openSheet(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${BODY}`).click();
  await page.getByTestId("stage-sheet").click();
}

async function pixel(page: Page): Promise<number[]> {
  return page.getByTestId("stack-canvas").evaluate((canvas: HTMLCanvasElement) => {
    return Array.from(canvas.getContext("2d")!.getImageData(2, 2, 1, 1).data);
  });
}

test("the board shows a Wearable under its body, with its cost", async ({ page, segmentingStudio: studio }) => {
  build(studio);
  await page.goto(studio.home);

  const row = page.getByTestId(`board-${HAIR}`);
  await expect(row).toHaveAttribute("data-body", BODY);
  await expect(row).toContainText("↳");
  // Under the body's row, and no Kind section of their own.
  await expect(page.locator(".board section h2", { hasText: "wearable" })).toHaveCount(0);
  await expect(page.getByTestId(`board-${CAP}`)).toHaveAttribute("data-body", BODY);
  await expect(page.getByTestId(`cost-${HAIR}`)).toContainText(/render \d+\.\d s/);
  await expect(page.getByTestId(`cost-${HAIR}`)).toContainText(/atlas \d+ x \d+ px/);
  await page.screenshot({ path: join(SHOTS, "wearables-board.png") });
});

test("the stack preview shows both Wearables, and the toggle changes the stacking", async ({ page, segmentingStudio: studio }) => {
  build(studio);
  paint(studio);
  await openSheet(page, studio);

  await expect(page.getByTestId("stack-preview")).toBeVisible();
  await expect(page.getByTestId(`stack-wearable-${HAIR}`)).toContainText("order 10");
  await expect(page.getByTestId(`stack-wearable-${CAP}`)).toContainText("order 20");
  await expect(page.getByTestId(`stack-cost-${CAP}`)).toContainText("atlas");
  const canvas = page.getByTestId("stack-canvas");
  await expect(canvas).toHaveAttribute("data-zoom", "4");
  await expect(canvas).toHaveAttribute("data-stacked", "3"); // the body and two Wearables

  // By order the cap (20) is on top of the hair (10): blue.
  await expect(canvas).toHaveAttribute("data-stack", "order");
  await expect.poll(() => pixel(page)).toEqual([41, 173, 255, 255]);
  // By depth the hair is nearest (10, against 50): green.
  await page.getByTestId("stack-depth").click();
  await expect(canvas).toHaveAttribute("data-stack", "depth");
  await expect.poll(() => pixel(page)).toEqual([0, 228, 54, 255]);
  await page.getByTestId("stack-order").click();
  await expect.poll(() => pixel(page)).toEqual([41, 173, 255, 255]);

  // Taking the cap off shows the hair by order too, and then the body (which is not green) with neither.
  await page.getByTestId(`stack-wear-${CAP}`).uncheck();
  await expect.poll(() => pixel(page)).toEqual([0, 228, 54, 255]);
  await page.getByTestId(`stack-wear-${HAIR}`).uncheck();
  await expect.poll(async () => (await pixel(page))[1]).toBeLessThan(200);
  await page.getByTestId(`stack-wear-${HAIR}`).check();
  await page.getByTestId(`stack-wear-${CAP}`).check();
  await page.screenshot({ path: join(SHOTS, "wearables-stack.png") });
});

test("wearable.stack_differs shows its box on the frame", async ({ page, segmentingStudio: studio }) => {
  build(studio);
  paint(studio);
  const { width } = farRight(studio);
  await openSheet(page, studio);

  await expect(page.getByTestId("stack-findings")).toContainText("differ");
  await page.getByTestId("stack-jump").click();
  const box = page.getByTestId("stack-box");
  await expect(box).toBeVisible();
  expect((await box.getAttribute("data-box"))!.split(",")[0]).toBe(String(width / 2));
  await page.screenshot({ path: join(SHOTS, "wearables-stack-differs.png") });
});
