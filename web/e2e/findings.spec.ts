// The flows of ticket 0093 (spec §11): findings a person reads. One next line, each finding once, info collapsed to a count.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, png, test, type Studio } from "./harness";

const ROOM = "room.alley";

test("a needs-review Stage shows one next line with a working button, and no error that repeats the status", async ({ page, studio }) => {
  studio.roomInReview();
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId("stage-fit").click();
  await expect(page.getByTestId("stage-fit")).toHaveAttribute("data-status", "needs-review");

  await expect(page.getByTestId("next-hint")).toHaveCount(1);
  await expect(page.getByTestId("finding-stage.needs_review")).toHaveCount(0);

  await page.getByTestId("next-accept").click();
  await expect(page.getByTestId("stage-fit")).not.toHaveAttribute("data-status", "needs-review");
});

const PROP = "prop.bench";
const GREEN: [number, number, number, number] = [0, 255, 0, 255];
const RED: [number, number, number, number] = [255, 0, 77, 255];

// A prop built down to the footprint, which waits for the Owner.
function builtProp(studio: Studio): void {
  studio.kiripix("new", "prop", "bench");
  studio.kiripix("set", PROP, "brief", "width=16", "height=16");
  studio.kiripix("set", PROP, "fit", "scale=2");
  const source = png(32, 32, (x, y) => (x >= 6 && x < 26 && y >= 8 && y < 28 ? RED : GREEN));
  studio.kiripix("pick", PROP, studio.importVariant(PROP, "bench.png", source));
  studio.run(PROP);
}

test("an info finding of a Run is a count that expands on a click", async ({ page, studio }) => {
  builtProp(studio);
  // A Godot project to export into: the built prop is then behind it, and `run` says so.
  mkdirSync(join(studio.cwd, "game"));
  writeFileSync(join(studio.cwd, "game", "project.godot"), "config_version=5\n");
  const settings = join(studio.cwd, "kiripix.toml");
  writeFileSync(
    settings,
    readFileSync(settings, "utf-8").replace('# project = "C:/Workspace/my-game"   # the Godot project to export into', 'project = "game"'),
  );
  const footprint = { decision: "footprint", data: { polygon: [[3, 12], [12, 12], [12, 14]], origin: [8, 14] } };
  studio.kiripix("decide", PROP, "footprint", "--decision", JSON.stringify(footprint));
  await page.goto(studio.home);
  await page.getByTestId(`asset-${PROP}`).click();
  await page.getByTestId("stage-footprint").click();
  const ran = page.waitForResponse((response) => response.url().includes("/api/run"));
  await page.getByTestId("run").click();
  const findings = ((await (await ran).json()) as { findings: { code: string; severity: string }[] }).findings;
  expect(findings.some((finding) => finding.code === "export.pending" && finding.severity === "info")).toBe(true);

  const toggle = page.getByTestId("notice-info");
  await expect(toggle).toHaveText("Show 1 note");
  await expect(page.getByTestId("finding-export.pending")).toHaveCount(0);
  await toggle.click();
  await expect(page.getByTestId("finding-export.pending")).toBeVisible();
  await expect(toggle).toHaveText("Hide 1 note");
});

test("a finding that a Run and the Stage's Checks both give shows once", async ({ page, studio }) => {
  builtProp(studio);
  await page.goto(studio.home);
  await page.getByTestId(`asset-${PROP}`).click();
  await page.getByTestId("stage-cutout").click();
  await page.getByTestId("param-chroma").fill("#FF00FF");
  await page.getByTestId("param-chroma").press("Enter");
  await expect(page.getByTestId("stage-cutout")).toHaveAttribute("data-status", "stale");
  const ran = page.waitForResponse((response) => response.url().includes("/api/run"));
  await page.getByTestId("run").click();
  // The Run's own result carries it, and so do the Checks: two lists that today would both show it.
  const findings = ((await (await ran).json()) as { findings: { code: string }[] }).findings;
  expect(findings.some((finding) => finding.code === "cutout.chroma_keyed_nothing")).toBe(true);

  await expect(page.getByTestId("checks").getByTestId("finding-cutout.chroma_keyed_nothing")).toBeVisible();
  await expect(page.getByTestId("finding-cutout.chroma_keyed_nothing")).toHaveCount(1);
  await expect(page.getByTestId("notice").getByTestId("finding-cutout.chroma_keyed_nothing")).toHaveCount(0);
  // What only the Run reported still shows, and the status-repeating error of the waiting footprint Stage does not.
  await expect(page.getByTestId("notice").getByTestId("finding-palette.mapping_error")).toBeVisible();
  await expect(page.getByTestId("finding-stage.needs_input")).toHaveCount(0);
});
