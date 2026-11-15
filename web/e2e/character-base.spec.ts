// Ticket 0227 (spec §6.3, ADR 0012, 0165, 0224): a character made from a base, and a generated one, against a real `kiripix
// serve` on a temporary Project and the fake Blender of tests/fixtures. The base's clips, files and parameters show as the
// base's; the Owner changes or removes them here, and the base never changes.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Studio } from "./harness";

const BODY = "character.zed";
const GUARD = "character.guard";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");
const SHOTS = join(import.meta.dirname, "..", "test-results");
const ACTIONS = [{ name: "Armature|mixamo.com|Layer0", start: 1, end: 31, travel: 0 }];
const BONES = ["root", ...["Hips", "Spine", "Spine1", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "RightShoulder", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"].map((name) => `mixamorig:${name}`)];

function clip(studio: Studio, asset: string, data: Record<string, unknown>, decision = "clip"): void {
  studio.kiripix("decide", asset, "clips", "--decision", JSON.stringify({ decision, data }));
}

// The base `zed`: the rigged fixture, idle and walk (actions of its Model) and wave (a clip-source file), built to `clips`.
function body(studio: Studio): void {
  studio.kiripix("new", "character", "zed");
  const variant = studio.json("import", BODY, join(CHARACTERS, "rigged.glb")).data.variant as string;
  studio.kiripix("pick", BODY, variant);
  studio.kiripix("import", BODY, studio.write("wave.fbx", Buffer.from(JSON.stringify({ actions: ACTIONS }))), "--role", "clip-source");
  clip(studio, BODY, { name: "idle", source: "idle", start: 0, end: 24, fps: 12, loop: true });
  clip(studio, BODY, { name: "walk", source: "walk", start: 0, end: 30, fps: 10, loop: true });
  clip(studio, BODY, { name: "wave", source: "wave", start: 1, end: 31, fps: 10, loop: false });
  studio.kiripix("set", BODY, "render", "bands=4");
  for (const stage of ["model", "rig", "clips"]) studio.kiripix("run", BODY, stage);
}

// A character made from the base, with a Model of its own on the base's skeleton.
function guard(studio: Studio, bones: string[] = BONES): void {
  studio.kiripix("new", "character", "guard", "--base", BODY);
  const variant = studio.json("import", GUARD, studio.write("guard.glb", Buffer.from(JSON.stringify({ bones, source_height: 1.62 })))).data.variant as string;
  studio.kiripix("pick", GUARD, variant);
}

function decisions(studio: Studio, asset: string, stage: string): { name: string; data: Record<string, unknown>; from_base: boolean }[] {
  const stages = studio.json("show", asset).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown>; from_base: boolean }[] }[];
  return stages.find((entry) => entry.stage === stage)!.decisions;
}

test("a character made from a base shows its base, the base's clips and a parameter with its mark; removing a base clip records a remove", async ({
  page,
  segmentingStudio: studio,
}) => {
  body(studio);
  guard(studio);
  await page.goto(`${studio.home}`);
  await page.getByTestId(`asset-${GUARD}`).click();

  // The Model screen links to the base, and a Stage shows what the character takes from it.
  await page.getByTestId("stage-model").click();
  await expect(page.getByTestId("base-link")).toHaveText(BODY);

  await page.getByTestId("stage-render").click();
  await expect(page.getByTestId("param-bands")).toHaveValue("4");
  await expect(page.getByTestId("param-origin-bands")).toContainText("from the base");
  await page.screenshot({ path: join(SHOTS, "character-base-render.png") });
  await page.getByTestId("param-set-bands").click(); // "set here": the character holds the value itself
  await expect(page.getByTestId("param-origin-bands")).toHaveCount(0);
  expect(studio.json("show", GUARD).data.params).toEqual({ base: BODY });
  const stages = studio.json("show", GUARD).data.stages as { stage: string; param_sources: Record<string, string> }[];
  expect(stages.find((entry) => entry.stage === "render")!.param_sources.bands).toBe("asset");

  // The clips: the base's, read-only, each to change here or remove here.
  await page.getByTestId("stage-clips").click();
  for (const name of ["idle", "walk", "wave"]) {
    await expect(page.getByTestId(`clip-base-${name}`)).toBeVisible();
    await expect(page.getByTestId(`clip-remove-${name}`)).toBeVisible();
  }
  await expect(page.getByTestId("clip-source-base-wave")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "character-base-clips.png") });

  await page.getByTestId("clip-remove-walk").click();
  await expect(page.getByTestId("clip-row-walk")).toHaveCount(0);
  expect(decisions(studio, GUARD, "clips").filter((d) => !d.from_base).map((d) => [d.name, d.data])).toEqual([["remove", { name: "walk" }]]);
  expect(decisions(studio, BODY, "clips").map((d) => d.data.name)).toEqual(["idle", "walk", "wave"]); // the base is untouched

  // Change here: a clip Decision of the same name, and the row is the character's own.
  await page.getByTestId("clip-edit-idle").click();
  await page.getByTestId("clip-end").fill("12");
  await page.getByTestId("clip-add").click();
  await expect(page.getByTestId("clip-row-idle")).toContainText("0–12");
  await expect(page.getByTestId("clip-base-idle")).toHaveCount(0);
  await expect(page.getByTestId("clip-base-wave")).toBeVisible();

  // Undo takes back only the character's own Decisions (the base's are never undone).
  await page.getByRole("button", { name: "Undo" }).click();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId("clip-row-walk")).toBeVisible();
  await expect(page.getByTestId("decision-count")).toHaveText("3 Decision(s)");
});

test("a character made from a base needs no Mixamo trip, and a Model off the base's skeleton shows the bones", async ({ page, segmentingStudio: studio }) => {
  body(studio);
  guard(studio, ["root", "mixamorig:Hips"]);
  studio.run(GUARD);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${GUARD}`).click();
  await page.getByTestId("stage-rig").click();
  await expect(page.getByTestId("base-rig-note")).toBeVisible();
  await expect(page.getByTestId("rigged-drop")).toHaveCount(0);
  await expect(page.getByTestId("mixamo-steps")).toHaveCount(0);
  await expect(page.getByTestId("stage-rig")).toHaveAttribute("data-status", "failed");
  await expect(page.getByTestId("base-mismatch")).toHaveAttribute("data-code", "rig.base_mismatch");
  await expect(page.getByTestId("base-mismatch")).toContainText(`the one of its base ${BODY}`);
  await expect(page.getByTestId("base-mismatch")).toContainText("mixamorig:Head");
  await page.screenshot({ path: join(SHOTS, "character-base-rig.png") });
});

test("a new character is made from a base in the UI", async ({ page, segmentingStudio: studio }) => {
  body(studio);
  await page.goto(studio.home);
  await page.getByTestId("new-character-name").fill("scout");
  await page.getByTestId("new-character-base").selectOption(BODY);
  await page.getByTestId("new-character-create").click();
  await expect(page.getByTestId("base-link")).toHaveText(BODY);
  expect(studio.json("show", "character.scout").data.base).toBe(BODY);
  await page.getByTestId("base-link").click();
  await expect(page.getByTestId("stage-title")).toBeVisible();
  await expect(page.getByTestId("base-link")).toHaveCount(0); // the base itself has no base
});

test("a generated character's Model screen shows its parameter file and offers no Pick", async ({ page, segmentingStudio: studio }) => {
  const folder = join(studio.cwd, "chargen");
  const settings = join(studio.cwd, "kiripix.toml");
  writeFileSync(settings, `${readFileSync(settings, "utf-8")}\n[character.generators.chargen]\nscript = "chargen/generate.py"\nlibrary = ["chargen/library.json"]\n`);
  mkdirSync(folder);
  writeFileSync(join(folder, "generate.py"), "print('fake')\n");
  writeFileSync(join(folder, "library.json"), JSON.stringify({ bones: BONES }));
  studio.write("elder.toml", Buffer.from('name = "elder"\nheight = 0.9\n'));
  studio.kiripix("new", "character", "elder", "--from-parameters", "incoming/elder.toml");

  await page.goto(studio.home);
  await page.getByTestId("asset-character.elder").click();
  await page.getByTestId("stage-model").click();
  await expect(page.getByTestId("parameters-name")).toHaveText("elder.toml");
  await expect(page.getByTestId("model-list")).toHaveCount(0);
  await expect(page.getByTestId("model-drop")).toHaveCount(0);
  await expect(page.locator(".model-row")).toHaveCount(0);

  // A dropped parameter file replaces it (import --role parameters).
  await page.getByTestId("parameters-drop-input").setInputFiles({ name: "elder.toml", mimeType: "application/toml", buffer: Buffer.from('name = "elder"\nheight = 0.8\n') });
  await expect.poll(() => (studio.json("show", "character.elder").data.parameters as { size: number }).size).toBe(Buffer.byteLength('name = "elder"\nheight = 0.8\n'));
  await page.screenshot({ path: join(SHOTS, "character-generated-model.png") });
});
