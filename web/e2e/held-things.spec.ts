// The flows of ticket 0306 (spec §6.3, §11): a character's held things on the clips screen, and the socket's point on the frames.
// Blender is the fake one of tests/fixtures; its rig has the bone `mixamorig:RightForeArm`, named in `blender-bones` for the render.

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./harness";

const HERO = "character.hero";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");
const SOCKET = "mixamorig:RightForeArm";

test.setTimeout(150_000);

test("a thing is imported, a clip holds it as one Decision, and its socket's point shows on the frames", async ({ page, segmentingStudio: studio }) => {
  studio.kiripix("new", "character", "hero");
  studio.kiripix("pick", HERO, studio.json("import", HERO, join(CHARACTERS, "rigged.glb")).data.variant as string);
  studio.run(HERO);
  writeFileSync(join(studio.cwd, "blender-bones"), JSON.stringify(["root", SOCKET]));
  const clip = { name: "hit", source: "walk", start: 0, end: 6, fps: 15, loop: false };
  studio.kiripix("decide", HERO, "clips", "--decision", JSON.stringify({ decision: "clip", data: clip }));

  await page.goto(studio.home);
  await page.getByTestId(`asset-${HERO}`).click();
  await page.getByTestId("stage-clips").click();
  await expect(page.getByTestId("things-empty")).toBeVisible();

  // Import: the thing is named first, then its mesh dropped.
  await page.getByTestId("thing-id").fill("phone");
  await page.getByTestId("thing-drop-input").setInputFiles(join(CHARACTERS, "render_thing.glb"));
  await expect(page.getByTestId("thing-phone")).toBeVisible();

  // Hold it: one `decide` of the clip with `attach`.
  await page.getByTestId("clip-edit-hit").click();
  await page.getByTestId("clip-attach-add").click();
  await page.getByTestId("clip-attach-socket-0").fill(SOCKET);
  await page.getByTestId("clip-attach-offset-y-0").fill("0.01");
  await page.getByTestId("clip-add").click();
  await expect(page.getByTestId("clip-holds-hit")).toHaveText(`phone at ${SOCKET}`);
  const stages = studio.json("show", HERO).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  const decided = stages.find((entry) => entry.stage === "clips")!.decisions.map((decision) => decision.data).filter((data) => data.name === "hit").at(-1)!;
  expect(decided.attach).toEqual([{ thing: "phone", socket: SOCKET, offset: [0, 0.01, 0] }]);
  await expect(page.getByTestId("thing-held-by-phone")).toBeVisible();
  await expect(page.getByTestId("thing-remove-phone")).toBeDisabled();

  // The render draws it and records a point at the socket, named after the bone.
  studio.run(HERO);
  const record = JSON.parse(readFileSync(join(studio.cwd, "assets", "character", "hero", "work", "render", "render.json"), "utf-8"));
  const frames = record.clips.find((c: { name: string }) => c.name === "hit").directions.s;
  await page.getByTestId("stage-render").click();
  await expect(page.getByTestId("frame-view")).toBeVisible();
  const mark = page.getByTestId("frame-canvas-point-rightforearm");
  await expect(mark).toHaveAttribute("data-x", String(Math.floor(frames[0].points.rightforearm.x)));
  await expect(mark).toHaveAttribute("data-y", String(Math.floor(frames[0].points.rightforearm.y)));
  await page.getByTestId("frame-view").screenshot({ path: join(import.meta.dirname, "..", "shots", "0306-held-thing-point.png") });

  // Letting go is one more `decide` of the clip, without `attach`.
  await page.getByTestId("stage-clips").click();
  await page.getByTestId("clip-edit-hit").click();
  await page.getByTestId("clip-attach-remove-0").click();
  await page.getByTestId("clip-add").click();
  await expect(page.getByTestId("clip-holds-hit")).toHaveText("");

  // A thing no clip holds is removed with `thing-remove`.
  await page.getByTestId("thing-id").fill("stick");
  await page.getByTestId("thing-drop-input").setInputFiles(join(CHARACTERS, "render_thing.glb"));
  await expect(page.getByTestId("thing-stick")).toBeVisible();
  await expect(page.getByTestId("thing-held-by-stick")).toHaveCount(0);
  await page.screenshot({ path: join(import.meta.dirname, "..", "shots", "0306-held-things.png") });
  await page.getByTestId("thing-remove-stick").click();
  await expect(page.getByTestId("thing-stick")).toHaveCount(0);
});
