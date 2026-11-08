// The flows of ticket 0083 (spec §11): a click is answered at once, whether or not the server has replied. The responses are held
// back with `page.route`, so the wait can be seen: the status strip, the working button and the marks on the canvas.

import type { Page, Route } from "@playwright/test";
import { art, expect, test, type Studio } from "./harness";

const ROOM = "room.alley";

// Requests matching a pattern wait here until `release`.
function hold(page: Page, pattern: string): Promise<{ release: () => void; seen: () => number }> {
  let count = 0;
  const waiting: Route[] = [];
  let open = false;
  return page
    .route(pattern, async (route) => {
      count++;
      if (open) await route.continue();
      else waiting.push(route);
    })
    .then(() => ({
      release: () => {
        open = true;
        for (const route of waiting.splice(0)) void route.continue();
      },
      seen: () => count,
    }));
}

function builtRoom(studio: Studio): void {
  studio.room();
  studio.kiripix("pick", ROOM, studio.importVariant(ROOM, "a.png", art(24)));
  studio.run(ROOM);
}

async function openStage(page: Page, studio: Studio, stage: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId(`stage-${stage}`).click();
  await expect(page.getByTestId("stage-title")).toHaveText(stage);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
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

const strip = (page: Page) => page.getByTestId("work-strip");

test("opening the room list and a room show the strip before the response", async ({ page, studio }) => {
  studio.room();
  await page.goto(studio.home);
  await expect(page.getByTestId(`asset-${ROOM}`)).toBeVisible();
  await expect(strip(page)).toHaveCount(0);

  const status = await hold(page, "**/api/status");
  await page.getByTestId(`asset-${ROOM}`).click();
  await expect(page.getByTestId("work-label")).toHaveText(`Opening ${ROOM}`);
  await expect(page.getByTestId("work-elapsed")).toBeVisible();
  status.release();
  await expect(strip(page)).toHaveCount(0);
  await expect(page.getByTestId("stage-title")).toBeVisible();

  const again = await hold(page, "**/api/status");
  await page.getByTestId("home").click();
  await expect(page.getByTestId("work-label")).toHaveText("Opening the room list");
  again.release();
  await expect(strip(page)).toHaveCount(0);
});

test("Accept shows the strip and a working button before the response, and a second press sends no second request", async ({
  page,
  studio,
}) => {
  studio.roomInReview();
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  const accept = page.getByTestId("accept");
  await expect(accept).toBeVisible();

  const held = await hold(page, "**/api/accept");
  await accept.click();
  await expect(page.getByTestId("work-label")).toHaveText("Accepting fit");
  await expect(accept).toBeDisabled();
  await expect(accept).toHaveText("Accepting…");
  await accept.click({ force: true }).catch(() => undefined);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(200);
  expect(held.seen()).toBe(1);

  held.release();
  await expect(strip(page)).toHaveCount(0);
  await expect(page.getByTestId("stage-fit")).not.toHaveAttribute("data-status", "needs-review");
});

test("a failed action clears the strip and shows its finding", async ({ page, studio }) => {
  studio.roomInReview();
  await page.goto(studio.url); // no session token: Accept is refused
  await page.getByTestId(`asset-${ROOM}`).click();
  const held = await hold(page, "**/api/accept");
  await page.getByTestId("accept").click();
  await expect(strip(page)).toBeVisible();
  held.release();
  await expect(page.getByTestId("notice")).toContainText("owner");
  await expect(strip(page)).toHaveCount(0);
  await expect(page.getByTestId("accept")).toBeEnabled();
});

test("a layer click leaves a mark on its pixel until the result lands", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await openStage(page, studio, "layers");
  const canvas = page.getByTestId("canvas");
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.keyboard.press("c");

  const held = await hold(page, "**/api/decide");
  await clickPixel(page, 20, 16);
  await expect(canvas).toHaveAttribute("data-pending-marks", "point");
  await expect(page.getByTestId("work-label")).toHaveText("Lifting into lamp");
  held.release();
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect(canvas).toHaveAttribute("data-pending-marks", "");
  await expect(strip(page)).toHaveCount(0);
});

test("three quick layer clicks all reach the journal in order, and the waiting count falls", async ({
  page,
  segmentingStudio: studio,
}) => {
  builtRoom(studio);
  await openStage(page, studio, "layers");
  await page.getByTestId("layer-id").fill("lamp");
  await page.getByTestId("layers-panel").click({ position: { x: 2, y: 2 } });
  await page.keyboard.press("c");
  await page.route("**/api/decide", async (route) => {
    await new Promise((done) => setTimeout(done, 700));
    await route.continue();
  });

  const seen: string[] = [];
  const watch = setInterval(() => {
    void page
      .getByTestId("work-waiting")
      .textContent({ timeout: 200 })
      .then((text) => text && seen.push(text.trim()))
      .catch(() => undefined);
  }, 100);
  await clickPixel(page, 20, 16);
  await clickPixel(page, 22, 12);
  await clickPixel(page, 24, 14);
  await expect(page.getByTestId("work-waiting")).toHaveText("2 waiting");
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)", { timeout: 30_000 });
  clearInterval(watch);
  expect(seen).toContain("2 waiting");
  expect(seen).toContain("1 waiting");
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: { x: number } }[] }[];
  expect(stages.find((entry) => entry.stage === "layers")!.decisions.map((entry) => entry.data.x)).toEqual([20, 22, 24]);
});

test("a brush stroke stays drawn, marked as pending, until the Stage has rebuilt", async ({ page, segmentingStudio: studio }) => {
  builtRoom(studio);
  await openStage(page, studio, "masks");
  const canvas = page.getByTestId("canvas");
  await page.keyboard.press("b");

  const decide = await hold(page, "**/api/decide");
  const run = await hold(page, "**/api/run");
  await dragPixel(page, [10, 8], [30, 8]);
  await expect(canvas).toHaveAttribute("data-pending-marks", "stroke");
  decide.release();
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect.poll(run.seen).toBe(1);
  await expect(canvas).toHaveAttribute("data-pending-marks", "stroke"); // the Stage hasn't rebuilt yet
  run.release();
  await expect(canvas).toHaveAttribute("data-pending-marks", "");
  await expect(strip(page)).toHaveCount(0);
});

test("run shows the strip with the elapsed time rising and an animation, with no progress event, and Cancel clears it", async ({
  page,
  studio,
}) => {
  studio.room();
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await expect(page.getByTestId("run")).toBeVisible();

  let cancelled = false;
  await page.route("**/api/jobs/*/cancel", async (route) => {
    cancelled = true;
    await route.continue();
  });
  let held: Route | null = null;
  await page.route("**/api/run", (route) => {
    held = route;
  });
  await page.getByTestId("run").click();
  await expect(page.getByTestId("work-label")).toHaveText(`Running ${ROOM}`);
  await expect(page.getByTestId("work-progress")).toHaveCount(0);
  await expect(page.getByTestId("work-bar")).toHaveCount(0);
  const running = await page.getByTestId("work-anim").evaluate((element) => element.getAnimations().length);
  expect(running).toBeGreaterThan(0);
  await expect(page.getByTestId("work-elapsed")).toHaveText(/^[1-9]\d* s$/);

  await page.getByTestId("cancel").click();
  await expect.poll(() => cancelled).toBe(true);
  await (held as Route | null)!.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ api_version: 1, ok: false, data: null, findings: [] }),
  });
  await expect(strip(page)).toHaveCount(0);
  await expect(page.getByTestId("cancel")).toHaveCount(0);
});
