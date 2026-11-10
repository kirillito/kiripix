// The flows of ticket 0114 (spec §6.3, §11): a character's model, rig and clips screens, against a real `kiripix serve` on
// a temporary Project. Blender is the fake one of tests/fixtures (the `segmentingStudio` fixture loads it); what only the
// real Blender can show (a real Model's bounds, a real rigged file's actions) is covered by the Python `blender` tests.

import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, test, type Studio } from "./harness";

const HERO = "character.hero";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");

function stage(page: Page, name: string) {
  return page.getByTestId(`stage-${name}`);
}

async function open(page: Page, studio: Studio, stageName?: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${HERO}`).click();
  if (stageName) await stage(page, stageName).click();
}

function importModel(studio: Studio, file: string): void {
  studio.kiripix("new", "character", "hero");
  const variant = studio.json("import", HERO, join(CHARACTERS, file)).data.variant as string;
  studio.kiripix("pick", HERO, variant);
}

// A character whose Model brings its own rig, built through `rig`.
function rigged(studio: Studio): void {
  importModel(studio, "rigged.glb");
  studio.run(HERO);
}

function decisions(studio: Studio, stageName: string): Record<string, unknown>[] {
  const stages = studio.json("show", HERO).data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === stageName)!.decisions.map((decision) => decision.data);
}

async function addClip(page: Page, name: string, source: string, fps: string): Promise<void> {
  await page.getByTestId("clip-name").fill(name);
  await page.getByTestId("clip-source").fill(source);
  await page.getByTestId("clip-fps").fill(fps);
  await page.getByTestId("clip-add").click();
}

test("a Model is imported and picked, and its bounds show once the Stage has run", async ({ page, segmentingStudio: studio }) => {
  studio.kiripix("new", "character", "hero");
  await open(page, studio, "model");
  await expect(page.getByTestId("model-screen")).toBeVisible();

  await page.getByTestId("model-drop-input").setInputFiles([join(CHARACTERS, "no_rig.glb"), join(CHARACTERS, "rigged.fbx")]);
  const rows = page.locator(".model-row");
  await expect(rows).toHaveCount(2);
  await expect(page.locator('[data-testid^="variant-size-"]').first()).toHaveText(/(B|KB|MB)$/);

  await page.keyboard.press("2");
  await expect(rows.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(rows.nth(0)).toHaveAttribute("aria-pressed", "false");
  await page.keyboard.press("1");
  await expect(rows.nth(0)).toHaveAttribute("aria-pressed", "true");

  await page.getByTestId("run").click();
  await expect(stage(page, "model")).toHaveAttribute("data-status", "done");
  await expect(page.locator('[data-testid^="variant-bounds-"]').first()).toContainText("bounds 1.00 × 0.50 × 2.00");
});

test("a Model without a rig sends the Owner to Mixamo, and the rigged file is dropped back", async ({ page, segmentingStudio: studio }) => {
  importModel(studio, "no_rig.glb");
  studio.run(HERO);
  await open(page, studio);
  await expect(stage(page, "rig")).toHaveAttribute("data-status", "needs-input");
  await expect(page.getByTestId("rig-screen")).toBeVisible(); // `next` opens the Asset on the Stage it needs

  const steps = page.getByTestId("mixamo-steps").locator("li");
  await expect(steps).toHaveCount(4);
  await expect(steps.nth(0)).toContainText("Upload");
  await expect(steps.nth(3)).toContainText("--role rigged");
  await expect(page.getByTestId("upload-path")).toContainText("mixamo_upload.fbx");

  await page.getByTestId("rigged-drop-input").setInputFiles(join(CHARACTERS, "rigged.fbx"));
  await expect(page.getByTestId("rigged-file")).toBeVisible();
  await page.getByTestId("run").click();
  await expect(stage(page, "rig")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("rig-summary")).toContainText("The rigged file from Mixamo");
  await expect(page.getByTestId("rig-mapping")).toContainText("mixamorig:Hips");
  await expect(page.getByTestId("mixamo-steps")).toHaveCount(0);
});

test("a rig missing a bone gets a bone Decision from the form", async ({ page, segmentingStudio: studio }) => {
  importModel(studio, "no_rig.glb");
  studio.run(HERO);
  // A rigged file without a spine, as the fake Blender reads it from the JSON in the file.
  const bones = ["root", "Hips", "Head", "LeftArm", "RightArm", "LeftUpLeg", "RightUpLeg", "Torso"];
  studio.kiripix("import", HERO, studio.write("odd.fbx", Buffer.from(JSON.stringify({ bones }))), "--role", "rigged");
  await open(page, studio, "rig");
  await page.getByTestId("run").click();
  await expect(stage(page, "rig")).toHaveAttribute("data-status", "failed");
  await expect(page.getByTestId("notice")).toContainText("rig.bone_missing");

  await page.getByTestId("bone-role").selectOption("spine");
  await page.getByTestId("bone-name").fill("Torso");
  await page.getByTestId("bone-add").click();
  await expect(page.getByTestId("bone-decisions")).toContainText("spine → Torso");
  expect(decisions(studio, "rig")).toEqual([{ role: "spine", bone: "Torso" }]);
  await page.getByTestId("run").click();
  await expect(stage(page, "rig")).toHaveAttribute("data-status", "done");
});

test("two clips are recorded and one is undone", async ({ page, segmentingStudio: studio }) => {
  rigged(studio);
  await open(page, studio);
  await expect(page.getByTestId("clips-screen")).toBeVisible();
  await expect(stage(page, "clips")).toHaveAttribute("data-status", "needs-input");

  // The Model's own actions fill the range.
  await page.getByTestId("clip-source").fill("walk");
  await expect(page.getByTestId("clip-end")).toHaveValue("30");
  await addClip(page, "walk", "walk", "10");
  await expect(page.getByTestId("clip-row-walk")).toContainText("0–30");
  await page.getByTestId("clip-stationary").check();
  await addClip(page, "idle", "idle", "12");
  await expect(page.getByTestId("clip-row-idle")).toContainText("0–24");
  await expect(page.getByTestId("decision-count")).toHaveText("2 Decision(s)");
  expect(decisions(studio, "clips")).toEqual([
    { name: "walk", source: "walk", start: 0, end: 30, fps: 10, loop: true, stationary: false },
    { name: "idle", source: "idle", start: 0, end: 24, fps: 12, loop: true, stationary: true },
  ]);

  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");
  await expect(page.getByTestId("clip-row-idle")).toHaveCount(0);
  await expect(page.getByTestId("clip-row-walk")).toBeVisible();

  await page.getByTestId("run").click();
  await expect(stage(page, "clips")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("clip-row-walk")).toContainText("10"); // the built frame count
});

test("a clip name that ends in a direction is stopped, an animation file is dropped, and an agent's clip shows", async ({
  page,
  segmentingStudio: studio,
}) => {
  rigged(studio);
  await open(page, studio, "clips");
  await page.getByTestId("clip-name").fill("walk_sw");
  await page.getByTestId("clip-source").fill("walk");
  await expect(page.getByTestId("clip-problem")).toContainText("direction");
  await expect(page.getByTestId("clip-add")).toBeDisabled();

  const actions = [{ name: "wave", start: 1, end: 31, travel: 0 }];
  await page.getByTestId("clip-drop-input").setInputFiles(studio.write("wave.fbx", Buffer.from(JSON.stringify({ actions }))));
  await expect(page.getByTestId("clip-source-wave")).toBeVisible();

  // An agent adds a clip while the screen is open.
  const data = { name: "hit", source: "wave", start: 1, end: 6, fps: 15, loop: false };
  studio.kiripix("decide", HERO, "clips", "--decision", JSON.stringify({ decision: "clip", data }));
  await expect(page.getByTestId("clip-row-hit")).toContainText("once");
});
