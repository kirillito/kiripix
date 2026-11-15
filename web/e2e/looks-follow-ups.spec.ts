// Ticket 0209 (spec §11): the looks screen's exact difference and edit Variants, and the palette from its Command, against a real
// `kiripix serve`.

import { readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { art, expect, layeredRoom, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const GREEN: [number, number, number, number] = [0, 228, 54, 255];
const ORANGE: [number, number, number, number] = [255, 163, 0, 255];
const WHITE: [number, number, number, number] = [255, 255, 255, 255];
const GROUND = (x: number): [number, number, number, number] => (Math.floor(x / 2) < 24 ? [255, 0, 77, 255] : [29, 43, 83, 255]);

// The `layeredRoom`'s source (96 x 64: a crate at x 40 to 55, y 20 to 35 and a lamp at x 60 to 71, y 8 to 19), with the lamp
// green, and the crate orange too when `crate` is set: a redraw that the region doesn't cover.
function edit(crate: boolean): Buffer {
  const inCrate = (x: number, y: number) => x >= 40 && x < 56 && y >= 20 && y < 36;
  const inLamp = (x: number, y: number) => x >= 60 && x < 72 && y >= 8 && y < 20;
  return png(96, 64, (x, y) => (inLamp(x, y) ? GREEN : inCrate(x, y) ? (crate ? ORANGE : WHITE) : GROUND(x)));
}

function room(studio: Studio): void {
  layeredRoom(studio);
  studio.run(ROOM);
}

async function open(page: Page, studio: Studio): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-looks").click();
  await expect(page.getByTestId("stage-title")).toHaveText("looks");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await expect(page.getByTestId("look-panel")).toBeVisible();
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

// The colour the canvas shows at a target pixel, at its centre. The overlay is switched off first, so it is the picture's own.
async function colourAt(page: Page, x: number, y: number): Promise<string> {
  const canvas = page.getByTestId("canvas");
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  return canvas.evaluate(
    (element: HTMLCanvasElement, at: number[]) => {
      const [px, py] = at;
      return Array.from(element.getContext("2d")!.getImageData(px, py, 1, 1).data).join(",");
    },
    [left + Math.floor((x + 0.5) * zoom), top + Math.floor((y + 0.5) * zoom)],
  );
}

function journal(studio: Studio): { name: string; data: Record<string, unknown> }[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "looks")!.decisions;
}

// The built Look's region as "x,y" pixels, sorted: every pixel its pieces (plate and Layers) cover, read through the file route.
async function builtRegion(page: Page, studio: Studio, look: string): Promise<string[]> {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; outputs: string[] }[];
  const looksFile = stages.find((entry) => entry.stage === "looks")!.outputs.find((path) => path.endsWith("/looks.json"))!;
  const folder = looksFile.slice(0, looksFile.lastIndexOf("/"));
  const built = (JSON.parse(readFileSync(join(studio.cwd, looksFile), "utf-8")) as { looks: { id: string; box: number[]; plate: string | null; layers: { file: string }[] }[] }).looks.find((entry) => entry.id === look)!;
  const files = [...(built.plate ? [built.plate] : []), ...built.layers.map((layer) => layer.file)].map((file) => `files/${encodeURI(`${folder}/${file}`)}`);
  return page.evaluate(
    async ({ files, x, y }) => {
      const set = new Set<string>();
      for (const file of files) {
        const image = new Image();
        image.src = file;
        await image.decode();
        const canvas = document.createElement("canvas");
        [canvas.width, canvas.height] = [image.naturalWidth, image.naturalHeight];
        const context = canvas.getContext("2d")!;
        context.drawImage(image, 0, 0);
        const alpha = context.getImageData(0, 0, canvas.width, canvas.height).data;
        for (let py = 0; py < canvas.height; py++) {
          for (let px = 0; px < canvas.width; px++) if (alpha[(py * canvas.width + px) * 4 + 3] > 0) set.add(`${x + px},${y + py}`);
        }
      }
      return [...set].sort();
    },
    { files, x: built.box[0], y: built.box[1] },
  );
}

async function importEdit(page: Page, studio: Studio, look: string, crate: boolean): Promise<void> {
  await page.getByTestId("look-new").fill(look);
  const path = studio.write(`${look}.png`, edit(crate));
  await page.getByTestId("look-import-input").setInputFiles(path);
  await expect(page.getByTestId(`look-${look}`)).toBeVisible();
}


const EXTRA = "#010203";

// The Project palette moved to another file, with one colour more; the room is built after, so the Stages read the moved file too.
function movePalette(studio: Studio): void {
  const old = join(studio.cwd, "style", "palette.gpl");
  const moved = join(studio.cwd, "style", "moved.gpl");
  writeFileSync(moved, readFileSync(old, "utf-8").trimEnd() + `
  1   2   3	extra
`);
  renameSync(old, join(studio.cwd, "style", "unused.txt"));
  const toml = join(studio.cwd, "kiripix.toml");
  writeFileSync(toml, readFileSync(toml, "utf-8").replace('"style/palette.gpl"', '"style/moved.gpl"'));
}

test("the place screen's swatches come from the palette the setting names", async ({ page, studio }) => {
  test.setTimeout(180_000);
  movePalette(studio);
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-place").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
  await page.getByTestId("marker-type").selectOption("emitter");
  await clickPixel(page, 30, 16);
  await expect(page.getByTestId("emitter-panel")).toBeVisible();
  await expect(page.getByTestId(`palette-${EXTRA.toUpperCase()}`)).toBeVisible();
  await expect(page.getByTestId("palette-#FF004D")).toBeVisible();
});

test("the loops screen's swatches come from the palette the setting names", async ({ page, studio }) => {
  test.setTimeout(180_000);
  movePalette(studio);
  layeredRoom(studio);
  studio.run(ROOM);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-loops").click();
  await expect(page.getByTestId("loop-panel")).toBeVisible();
  await page.getByTestId("loop-new").fill("floor_glow");
  await page.getByTestId("loop-add").click();
  await expect(page.getByTestId("loop-floor_glow")).toBeVisible();
  await expect(page.getByTestId(`palette-${EXTRA}`)).toBeVisible();
  await expect(page.getByTestId("palette-#ff004d")).toBeVisible();
});

test("the previewed difference is the region the Look has once the Decision is built", async ({ page, studio }) => {
  test.setTimeout(180_000);
  room(studio);
  await open(page, studio);
  await importEdit(page, studio, "lamp_off", false);

  await page.keyboard.press("d");
  await page.getByTestId("look-tolerance").fill("3");
  await dragPixel(page, [26, 1], [40, 13]);
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-look-preview", /^[1-9]\d*$/);
  const previewed = Number(await canvas.getAttribute("data-look-preview"));
  // Moving the tolerance asks again: a coarser one can't hold more pixels.
  await page.getByTestId("look-tolerance").fill("20");
  await expect(canvas).toHaveAttribute("data-look-preview", /^\d+$/);
  const answer = page.waitForResponse((response) => response.url().endsWith("/api/probe") && (response.request().postData() ?? "").includes('"3"]'));
  await page.getByTestId("look-tolerance").fill("3");
  await expect(canvas).toHaveAttribute("data-look-preview", String(previewed));
  const preview = ((await (await answer).json()) as { data: { result: { runs: [number, number, number][] } } }).data.result.runs;
  const previewedPixels = preview.flatMap(([y, x, length]) => Array.from({ length }, (_, i) => `${x + i},${y}`)).sort();
  expect(previewedPixels).toHaveLength(previewed);
  await page.screenshot({ path: "test-results/looks-difference-preview.png" });
  expect(journal(studio)).toHaveLength(1); // a preview records nothing

  await page.getByTestId("difference-record").click();
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  await expect(page.getByTestId("look-list")).toContainText(/\d+ px change/);
  // The region the built Look holds, read from its pieces' alpha, has the previewed pixels (`changed` counts only the pixels whose colour moved).
  await expect(canvas).toHaveAttribute("data-masks", new RegExp(`region:${previewed}( |$)`));
  await expect(canvas).toHaveAttribute("data-look-preview", "");
  // Pixel by pixel: the built Look's region, from its pieces' alpha at its box, is the previewed one.
  expect(await builtRegion(page, studio, "lamp_off")).toEqual(previewedPixels);
});

test("an older edit is picked from the Look's list, and the toggle shows it", async ({ page, studio }) => {
  test.setTimeout(180_000);
  room(studio);
  await open(page, studio);
  await page.getByTestId("look-opacity").fill("0");
  await importEdit(page, studio, "lamp_off", true); // the crate orange
  await importEdit(page, studio, "lamp_off", false); // the crate white, picked last

  const variants = (studio.json("show", ROOM).data.looks as { look: string; variants: { name: string }[]; picked: string }[])[0];
  expect(variants.variants).toHaveLength(2);
  const first = variants.variants.map((entry) => entry.name).find((name) => name !== variants.picked)!;
  await expect(page.getByTestId(`look-variant-${variants.picked}`)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId(`look-variant-${first}`)).toHaveAttribute("aria-pressed", "false");

  await page.keyboard.press("g");
  for (const [x, y] of [[18, 8], [30, 8], [30, 20], [18, 20]]) await clickPixel(page, x, y);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("look-list")).toContainText(/\d+ px change/);
  await page.getByTestId("view-look").click();
  await expect.poll(() => colourAt(page, 24, 14)).toBe("255,241,232,255");

  await page.getByTestId(`look-variant-${first}`).click();
  await expect(page.getByTestId(`look-variant-${first}`)).toHaveAttribute("aria-pressed", "true");
  expect(studio.json("show", ROOM).data.looks).toMatchObject([{ picked: first }]);
  expect(journal(studio).at(-1)).toMatchObject({ name: "pick", data: { look: "lamp_off", variant: first } });
  await expect.poll(() => colourAt(page, 24, 14)).toBe("255,163,0,255");
  await page.screenshot({ path: "test-results/looks-variants.png" });
});
