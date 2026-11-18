// The flows of ticket 0245 (spec §6.7, §11): a portrait's emotion strip, flip in place with the shimmer boxes, and the `face`
// region, against a real `kiripix serve` on a temporary Project. The UI holds no logic: each action is one Command, and the
// checks read what the Commands recorded.

import type { Page } from "@playwright/test";
import { expect, png, test, type Studio } from "./harness";

const PORTRAIT = "portrait.sanjay";
const KEY: [number, number, number, number] = [30, 238, 24, 255];
const WIDTH = 128;
const HEIGHT = 160; // 4:5, so the 32 x 40 canvas is a whole scale of 4
const FACE = (x: number, y: number) => x >= 48 && x < 80 && y >= 40 && y < 72;

// Blocks of 8 px in colours that are neither the key nor near it, the same in every picture; the face is the one part that
// takes a seed.
function colour(x: number, y: number, seed: number): [number, number, number, number] {
  const hash = (((x >> 3) * 73856093) ^ ((y >> 3) * 19349663) ^ (seed * 83492791)) >>> 0;
  return [40 + (hash % 180), 40 + ((hash >> 8) % 180), 40 + ((hash >> 16) % 180), 255];
}

function figure(face: number): Buffer {
  return png(WIDTH, HEIGHT, (x, y) => (x >= 20 && x < 108 && y >= 30 ? colour(x, y, FACE(x, y) ? face : 0) : KEY));
}

// A portrait with the neutral and two emotions (`happy`, `sad`) built up to `upto`.
function portrait(studio: Studio, upto: string): void {
  studio.kiripix("new", "portrait", "sanjay");
  studio.kiripix("set", PORTRAIT, "brief", "width=32", "height=40");
  studio.kiripix("set", PORTRAIT, "cutout", "rim_reach=0", "spill_reach=0", "islands=0");
  studio.kiripix("pick", PORTRAIT, studio.importVariant(PORTRAIT, "neutral.png", figure(0)));
  for (const [id, face] of [["happy", 1], ["sad", 2]] as const) {
    studio.kiripix("decide", PORTRAIT, "source", "--decision", JSON.stringify({ decision: "emotion", data: { id } }));
    studio.write(`${id}.png`, figure(face));
    const variant = studio.json("import", PORTRAIT, `incoming/${id}.png`, "--emotion", id).data.variant as string;
    studio.kiripix("pick", PORTRAIT, variant, "--emotion", id);
  }
  for (const stage of ["brief", "source", "cutout", "register", "fit", "palette", "finish"]) {
    studio.kiripix("run", PORTRAIT, stage);
    if (stage === upto) break;
  }
}

async function open(page: Page, studio: Studio, stageName: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${PORTRAIT}`).click();
  await page.getByTestId(`stage-${stageName}`).click();
}

async function pixel(page: Page, x: number, y: number): Promise<{ x: number; y: number }> {
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  return { x: box.x + left + (x + 0.5) * zoom, y: box.y + top + (y + 0.5) * zoom };
}

// The colour on screen at an image pixel, so a flip is seen as the pixels it changes.
async function shown(page: Page, x: number, y: number): Promise<string> {
  const at = await pixel(page, x, y);
  const box = (await page.getByTestId("canvas").boundingBox())!;
  return page.getByTestId("canvas").evaluate(
    (element, point) => {
      const data = (element as HTMLCanvasElement).getContext("2d")!.getImageData(point.x, point.y, 1, 1).data;
      return `${data[0]},${data[1]},${data[2]}`;
    },
    { x: Math.round(at.x - box.x), y: Math.round(at.y - box.y) },
  );
}

function faces(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", PORTRAIT).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "register")!.decisions.filter((d) => d.name === "face").map((d) => d.data);
}

test("the strip shows the neutral and each emotion with its pick, and a key flips one over the neutral", async ({ page, studio }) => {
  portrait(studio, "cutout");
  await open(page, studio, "cutout");

  await expect(page.getByTestId("emotion-strip")).toBeVisible();
  for (const name of ["neutral", "happy", "sad"]) await expect(page.getByTestId(`emotion-${name}`)).toBeVisible();
  await expect(page.getByTestId("emotion-happy-pick")).toContainText("Variant ");
  await expect(page.getByTestId("emotion-neutral")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", `${WIDTH}x${HEIGHT}`);

  const before = await shown(page, 64, 56); // inside the face
  const body = await shown(page, 30, 120); // outside it
  await page.getByTestId("emotion-happy").click();
  await page.keyboard.press("v");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-flip", "happy");
  expect(await shown(page, 64, 56)).not.toEqual(before);
  expect(await shown(page, 30, 120)).toEqual(body);

  await page.keyboard.press("v");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-flip", "");
  expect(await shown(page, 64, 56)).toEqual(before);

  await page.keyboard.press("2");
  await expect(page.getByTestId("emotion-sad")).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: "shots/portrait-flip.png" });
});

test("a polygon and a brush stroke on register are each a face Decision in the neutral cutout's pixels", async ({ page, studio }) => {
  portrait(studio, "cutout");
  await open(page, studio, "register");
  await expect(page.getByTestId("face-summary")).toContainText("No face region");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", `${WIDTH}x${HEIGHT}`);

  for (const [x, y] of [[44, 36], [84, 36], [84, 76], [44, 76]]) {
    const at = await pixel(page, x, y);
    await page.mouse.click(at.x, at.y);
  }
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  expect(faces(studio)).toEqual([{ points: [[44, 36], [84, 36], [84, 76], [44, 76]] }]);
  await expect(page.getByTestId("face-summary")).toContainText("A face region is drawn"); // register ran again on its own

  await page.keyboard.press("b");
  const from = await pixel(page, 30, 100);
  const to = await pixel(page, 60, 100);
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, { steps: 4 });
  await page.mouse.up();
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  const stroke = faces(studio)[1];
  expect(stroke.radius).toBe(2);
  expect((stroke.points as number[][])[0]).toEqual([30, 100]);
  await page.screenshot({ path: "shots/portrait-face.png" });

  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
});

test("finish draws the shimmer boxes of the selected emotion, and the picture flips in place", async ({ page, studio }) => {
  portrait(studio, "finish");
  const shimmer = (studio.json("check", PORTRAIT) as unknown as { findings: { code: string; data: { emotion: string; boxes: { x: number }[] } }[] })
    .findings.find((finding) => finding.code === "portrait.shimmer" && finding.data.emotion === "happy");
  expect(shimmer?.data.boxes.length).toBeGreaterThan(0);

  await open(page, studio, "finish");
  await page.getByTestId("emotion-happy").click();
  const boxes = await page.getByTestId("canvas").getAttribute("data-shimmer");
  expect(boxes?.split(" ").length).toBe(shimmer!.data.boxes.length);
  await page.keyboard.press("v");
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-flip", "happy");
  await page.screenshot({ path: "shots/portrait-finish.png" });
});

test("an emotion is declared, imported and picked from the strip, each as a Command", async ({ page, studio }) => {
  studio.kiripix("new", "portrait", "sanjay");
  studio.kiripix("pick", PORTRAIT, studio.importVariant(PORTRAIT, "neutral.png", figure(0)));
  await open(page, studio, "source");

  await page.getByTestId("emotion-id").fill("happy");
  await page.getByTestId("emotion-declare").click();
  await expect(page.getByTestId("emotion-happy")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("emotion-happy-pick")).toContainText("no image picked");

  await page.getByTestId("emotion-import-input").setInputFiles(studio.write("happy.png", figure(1)));
  await expect(page.getByTestId("emotion-happy-pick")).toContainText("Variant ");
  const emotions = studio.json("show", PORTRAIT).data.emotions as { emotion: string; picked: string | null; current: boolean }[];
  expect(emotions.map((entry) => [entry.emotion, entry.picked !== null, entry.current])).toEqual([["happy", true, true]]);
});
