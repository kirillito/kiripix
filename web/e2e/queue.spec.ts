// The flows of ticket 0329 (spec §11): queue mode, one keyboard flow over every stop that waits on the Owner.

import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { art, expect, png, test, type Studio } from "./harness";

// A second room with its fit waiting for the Owner, as `roomInReview` makes the first.
function secondRoomInReview(studio: Studio): string {
  const id = "room.yard";
  studio.kiripix("new", "room", "yard", "--view", "top");
  studio.kiripix("set", id, "brief", "width=48", "height=32");
  studio.kiripix("set", id, "fit", "scale=2");
  studio.kiripix("pick", id, studio.importVariant(id, "y1.png", art(24)));
  studio.run(id);
  studio.write("ypaint.png", png(48, 32, (x, y) => (x === 1 && y === 1 ? [0, 0, 0, 255] : [0, 0, 0, 0])));
  studio.kiripix("override", id, "fit", "incoming/ypaint.png");
  studio.run(id);
  studio.kiripix("pick", id, studio.importVariant(id, "y2.png", art(10)));
  studio.run(id);
  return id;
}

// A demo Asset (the test Kind) whose copy Stage has a finding only the Owner can settle.
function ownerFinding(studio: Studio): void {
  studio.kiripix("new", "demo", "b");
  const src = join(studio.cwd, "assets", "demo", "b", "src");
  mkdirSync(src, { recursive: true });
  writeFileSync(join(src, "input.txt"), "owner", "utf-8");
  writeFileSync(join(src, "extra.txt"), "extra", "utf-8");
  studio.run("demo.b");
}

test("the Owner steps through two reviews and a finding by keyboard, accepts with A, and the queue ends empty", async ({ page, segmentingStudio: studio }) => {
  studio.roomInReview();
  secondRoomInReview(studio);
  ownerFinding(studio);
  await page.goto(studio.home);

  await expect(page.getByTestId("queue-open")).toHaveText("Queue · 3");
  await page.getByTestId("queue-open").click();
  await expect(page.getByTestId("queue-position")).toHaveText("1 of 3");
  // Asset ID order: demo.b (the finding), room.alley, room.yard.
  await expect(page.getByTestId("queue-type")).toHaveText("Finding");
  await expect(page.getByTestId("queue-owner-action")).toContainText("Decide what the text should say");

  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("queue-position")).toHaveText("2 of 3");
  await expect(page.getByTestId("queue-type")).toHaveText("Review");
  await expect(page.getByTestId("stage-title")).toHaveText("fit");
  await page.keyboard.press("n");
  await expect(page.getByTestId("queue-position")).toHaveText("3 of 3");
  await page.keyboard.press("p");
  await expect(page.getByTestId("queue-position")).toHaveText("2 of 3");

  // A accepts the review; the queue moves on to the next item still waiting.
  await expect(page.getByTestId("accept")).toBeVisible();
  await page.keyboard.press("a");
  await expect(page.getByTestId("queue-open")).toHaveText("Queue · 2");
  await expect(page.getByTestId("queue-position")).toHaveText("2 of 2");
  await expect(page.getByTestId("queue-type")).toHaveText("Review");
  await expect(page.getByTestId("stage-title")).toHaveText("fit");
  await expect(page.getByTestId("accept")).toBeVisible();
  await page.keyboard.press("a");
  await expect(page.getByTestId("queue-open")).toHaveText("Queue · 1");
  await expect(page.getByTestId("queue-type")).toHaveText("Finding");

  await page.screenshot({ path: "shots/queue-mode.png" });
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("queue-strip")).toHaveCount(0);
});

test("a note written by kiripix note shows on its item, and a match narrows the queue", async ({ page, studio }) => {
  studio.roomInReview();
  secondRoomInReview(studio);
  studio.kiripix("note", "room.yard", "fit", "check the left wall");
  await page.goto(studio.home);

  await page.getByTestId("queue-open").click();
  await expect(page.getByTestId("queue-position")).toHaveText("1 of 2");
  await expect(page.getByTestId("queue-notes")).toHaveCount(0);
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("queue-notes")).toContainText("check the left wall");

  await page.getByTestId("queue-match").fill("room.alley");
  await page.getByTestId("queue-match").press("Enter");
  await expect(page.getByTestId("queue-position")).toHaveText("1 of 1");
  await expect(page.getByTestId("queue-open")).toHaveText("Queue · 1");

  // An agent works behind the Owner: the note lands live.
  await page.getByTestId("queue-match").fill("");
  await page.getByTestId("queue-match").press("Enter");
  await expect(page.getByTestId("queue-position")).toHaveText("1 of 2");
  studio.kiripix("note", "room.alley", "fit", "agent says look at the door");
  await expect(page.getByTestId("queue-notes")).toContainText("agent says look at the door");
});
