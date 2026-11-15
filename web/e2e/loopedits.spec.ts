// Ticket 0221 (spec §6.1 and §11): the Edits source of a frame Loop, against a real `kiripix serve`. Two edits of the room's Source
// are imported (each is stored and picked for its frame), a `hold` is drawn over the top half of the Loop's region and built, and
// the built frames are equal there. Every action is one Command.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, layeredRoom, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const LOOP = "lamp_edit";

async function open(page: Page, studio: Studio): Promise<void> {
  layeredRoom(studio);
  studio.run(ROOM);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-loops").click();
  await expect(page.getByTestId("stage-title")).toHaveText("loops");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("loop-panel")).toBeVisible();
}

async function clickPixel(page: Page, x: number, y: number): Promise<void> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  await page.mouse.click(box.x + left + (x + 0.5) * zoom, box.y + top + (y + 0.5) * zoom);
}

function journal(studio: Studio): { name: string; data: Record<string, unknown> }[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "loops")!.decisions;
}

function built(studio: Studio): { loops: Record<string, unknown>[] } {
  return JSON.parse(readFileSync(join(studio.cwd, "assets", "room", "alley", "work", "loops", "loops.json"), "utf-8")) as { loops: Record<string, unknown>[] };
}

// The Source as `layeredRoom` makes it, doubled: the lamp is x 60 to 71, y 8 to 19 (target 30 to 35, 4 to 9). The edit gives the
// lamp's top half one colour and its bottom half another, both of the default palette.
function edit(top: [number, number, number, number], bottom: [number, number, number, number]): Buffer {
  const ground = (x: number): [number, number, number, number] => (Math.floor(x / 2) < 24 ? [255, 0, 77, 255] : [29, 43, 83, 255]);
  const crate = (x: number, y: number) => x >= 40 && x < 56 && y >= 20 && y < 36;
  const lamp = (x: number, y: number) => x >= 60 && x < 72 && y >= 8 && y < 20;
  return png(96, 64, (x, y) => (crate(x, y) ? [255, 255, 255, 255] : lamp(x, y) ? (y < 14 ? top : bottom) : ground(x)));
}
const YELLOW: [number, number, number, number] = [255, 236, 39, 255];
const GREEN: [number, number, number, number] = [0, 228, 54, 255];
const BLUE: [number, number, number, number] = [41, 173, 255, 255];
const WHITE: [number, number, number, number] = [255, 241, 232, 255];

// The rows of a frame's thumbnail, as text: one `r,g,b,a` a pixel.
async function rows(page: Page, frame: number): Promise<string[]> {
  return page.getByTestId(`frame-${frame}`).locator("canvas").evaluate((element) => {
    const canvas = element as HTMLCanvasElement;
    const data = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height).data;
    const out: string[] = [];
    for (let y = 0; y < canvas.height; y++) {
      const row: string[] = [];
      for (let x = 0; x < canvas.width; x++) row.push([...data.slice((y * canvas.width + x) * 4, (y * canvas.width + x) * 4 + 4)].join(","));
      out.push(row.join(" "));
    }
    return out;
  });
}

async function editsLoop(page: Page, studio: Studio): Promise<void> {
  await page.getByTestId("loop-new").fill(LOOP);
  await page.getByTestId("loop-new-form").selectOption("frames");
  await page.getByTestId("loop-add").click();
  await expect(page.getByTestId(`loop-${LOOP}`)).toBeVisible();
  await page.getByTestId("loop-opacity").fill("0");
  await page.keyboard.press("f");
  await clickPixel(page, 33, 6); // the lamp is the Loop's region
  await page.getByTestId("source-edits").click();
  await expect(page.getByTestId("edit-import")).toBeVisible();
  await expect(page.getByText("Edit the room's Source each time, not an earlier edit.")).toBeVisible();
  await expect.poll(() => journal(studio).some((entry) => entry.name === "frames" && entry.data.source === "edits")).toBe(true);
}

test("two edits are imported and picked, and a hold over the top half makes it equal in both built frames", async ({ page, studio }) => {
  await open(page, studio);
  await editsLoop(page, studio);

  studio.write("e1.png", edit(YELLOW, GREEN));
  studio.write("e2.png", edit(BLUE, WHITE));
  await expect(page.getByTestId("edit-frame")).toHaveValue("1");
  await page.getByTestId("edit-import-input").setInputFiles(join(studio.cwd, "incoming", "e1.png"));
  await expect(page.getByTestId("edit-frame")).toHaveValue("2");
  await page.getByTestId("edit-import-input").setInputFiles(join(studio.cwd, "incoming", "e2.png"));

  expect(journal(studio).filter((entry) => entry.name === "pick").map((entry) => entry.data.frame)).toEqual([1, 2]);
  await expect(page.getByTestId("loop-list")).toContainText("3 frames");
  await expect(page.getByTestId("frame-2")).toBeVisible();
  expect(built(studio).loops[0]).toMatchObject({ id: LOOP, source: "edits", frames: 3 });
  // Both frames redraw the whole region: the pair is flagged on both of its frames.
  await expect(page.getByTestId("frame-badge-1-loop.flicker")).toBeVisible();
  await expect(page.getByTestId("frame-badge-2-loop.flicker")).toBeVisible();

  const first = await rows(page, 1);
  const second = await rows(page, 2);
  expect(first[0]).not.toEqual(second[0]); // the top differs before a hold

  // A hold of frame 1 over the top half: a polygon, one Decision.
  await page.getByTestId("frame-hold-1").click();
  await page.keyboard.press("g");
  for (const [x, y] of [[28, 2], [38, 2], [38, 6], [28, 6]] as const) await clickPixel(page, x, y);
  const before = journal(studio).length;
  await page.keyboard.press("Enter");
  await expect.poll(() => journal(studio).length).toBe(before + 1);
  expect(journal(studio).at(-1)).toMatchObject({ name: "hold", data: { loop: LOOP, frame: 1 } });
  await expect(page.getByTestId("loop-list")).toContainText("px held");

  await expect.poll(async () => (await rows(page, 1))[0] === (await rows(page, 2))[0]).toBe(true);
  const heldFirst = await rows(page, 1);
  const heldSecond = await rows(page, 2);
  expect(heldFirst[0]).toEqual(heldSecond[0]);
  expect(heldFirst[1]).toEqual(heldSecond[1]);
  expect(heldFirst.at(-1)).not.toEqual(heldSecond.at(-1)); // the bottom still moves
  if (process.env.KIRIPIX_SCREENSHOT) await page.screenshot({ path: process.env.KIRIPIX_SCREENSHOT });
});

test("the Edits source needs a region to hold, and the Op and Kit sources stay", async ({ page, studio }) => {
  await open(page, studio);
  await page.getByTestId("loop-new").fill(LOOP);
  await page.getByTestId("loop-new-form").selectOption("frames");
  await page.getByTestId("loop-add").click();
  await expect(page.getByTestId("source-op")).toBeVisible();
  await expect(page.getByTestId("source-kit")).toBeVisible();
  await expect(page.getByTestId("source-edits")).toBeEnabled();
  await expect(page.getByText(/wait for trial 0184/)).toHaveCount(0);
});
