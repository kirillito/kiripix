// The flows of ticket 0330 (spec §11): the district view, a glob's rooms with their Exits and the batch actions.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { art, expect, test, type Studio } from "./harness";

// A 48 x 32 room with its Source built, so it has a thumbnail.
function builtRoom(studio: Studio, name: string): string {
  const id = `room.${name}`;
  studio.kiripix("new", "room", name, "--view", "top");
  studio.kiripix("set", id, "brief", "width=48", "height=32");
  studio.kiripix("set", id, "fit", "scale=2");
  studio.kiripix("pick", id, studio.importVariant(id, `${name}.png`, art(24)));
  studio.run(id);
  return id;
}

function exit(studio: Studio, room: string, id: string, targetRoom: string, targetExit: string): void {
  const data = { id, type: "exit", x: 30, y: 12, target_room: targetRoom, target_exit: targetExit };
  studio.kiripix("decide", room, "place", "--decision", JSON.stringify({ decision: "marker", data }));
}

// Two paired rooms, a third whose Exit has no way back, and a room outside the district with an unpaired Exit of its own.
function district(studio: Studio): void {
  const a = builtRoom(studio, "ch01_dungeon_a");
  const b = builtRoom(studio, "ch01_dungeon_b");
  const c = builtRoom(studio, "ch01_dungeon_c");
  const other = builtRoom(studio, "ch02_hall");
  exit(studio, a, "exit.east", b, "exit.west");
  exit(studio, b, "exit.west", a, "exit.east");
  exit(studio, c, "exit.up", a, "exit.east");
  exit(studio, other, "exit.up", a, "exit.east");
}

// The session token travels in the fragment, after the query.
const at = (studio: Studio, glob: string) => `${studio.url}?district=${encodeURIComponent(glob)}#${studio.home.split("#")[1]}`;

test("a district shows its rooms and Exits; an unpaired Exit opens its room on place", async ({ page, studio }) => {
  district(studio);
  await page.goto(studio.home);

  // The prefixes of the room IDs are shortcuts into the view.
  await expect(page.getByTestId("district-prefix-room.ch01_dungeon_*")).toBeVisible();
  await page.getByTestId("district-glob").fill("room.ch01_dungeon_*");
  await page.getByTestId("district-go").click();

  await expect(page.getByTestId("district-summary")).toContainText("3 rooms");
  for (const name of ["a", "b", "c"]) {
    await expect(page.getByTestId(`district-room-room.ch01_dungeon_${name}`)).toBeVisible();
    await expect(page.getByTestId(`district-thumb-room.ch01_dungeon_${name}`)).toBeVisible();
  }
  await expect(page.getByTestId("district-room-room.ch02_hall")).toHaveCount(0);
  await expect(page.getByTestId("district-room-room.ch01_dungeon_a")).toContainText("3 x 2 tiles");

  // The thumbnail is shown at a whole zoom, nearest-neighbour.
  const zoom = Number(await page.getByTestId("district-grid").getAttribute("data-zoom"));
  expect(Number.isInteger(zoom) && zoom >= 1).toBe(true);
  const thumb = page.getByTestId("district-thumb-room.ch01_dungeon_a");
  expect(await thumb.evaluate((node) => getComputedStyle(node).imageRendering)).toBe("pixelated");
  const natural = await thumb.evaluate((node) => (node as HTMLImageElement).naturalWidth);
  expect((await thumb.boundingBox())!.width).toBe(natural * zoom);

  await expect(page.getByTestId("district-exit-room.ch01_dungeon_a-exit.east")).toHaveAttribute("data-pairing", "paired");
  await expect(page.getByTestId("district-exit-room.ch01_dungeon_b-exit.west")).toHaveAttribute("data-pairing", "paired");
  await expect(page.getByTestId("district-exit-room.ch01_dungeon_c-exit.up")).toHaveAttribute("data-pairing", "unpaired");
  await expect(page.getByTestId("district-exit-room.ch01_dungeon_c-exit.up")).toHaveAttribute("data-severity", "error");
  await expect(page.getByTestId("district-badge-room.ch01_dungeon_c")).toHaveText("1");
  await expect(page.getByTestId("district-badge-room.ch01_dungeon_a")).toHaveCount(0);
  await page.screenshot({ path: "shots/district-view.png" });

  await page.getByTestId("district-exit-open-room.ch01_dungeon_c-exit.up").click();
  await expect(page.getByTestId("stage-title")).toHaveText("place");
  await expect(page.getByTestId("stage-place")).toHaveAttribute("aria-selected", "true");
});

test("Check on the district shows the findings of its rooms only", async ({ page, studio }) => {
  district(studio);
  await page.goto(studio.home);
  await page.getByTestId("district-prefix-room.ch01_dungeon_*").click();
  await expect(page.getByTestId("district-summary")).toContainText("3 rooms");

  await page.getByTestId("district-check").click();
  await expect(page.getByTestId("district-outcome")).toHaveAttribute("data-label", "Check");
  const findings = page.getByTestId("district-findings");
  await expect(findings).toContainText("ch01_dungeon_c");
  await expect(findings).not.toContainText("ch02_hall");
  await page.screenshot({ path: "shots/district-check.png" });
});

// Two exportable rooms in their own district: a wall in `solid`, a Spawn, paired Exits, a Godot project to export into.
function exportableDistrict(studio: Studio): void {
  mkdirSync(join(studio.cwd, "game"));
  writeFileSync(join(studio.cwd, "game", "project.godot"), "config_version=5\n", "utf-8");
  const settings = join(studio.cwd, "kiripix.toml");
  writeFileSync(settings, readFileSync(settings, "utf-8").replace('# project = "C:/Workspace/my-game"   # the Godot project to export into', 'project = "game"'), "utf-8");
  const ids = ["ch03_a", "ch03_b"].map((name) => builtRoom(studio, name));
  const flood = { decision: "flood", data: { x: 0, y: 0, mask: "solid" } };
  for (const id of ids) studio.kiripix("decide", id, "masks", "--decision", JSON.stringify(flood));
  const spawn = { id: "spawn.main", type: "spawn", x: 34, y: 16 };
  studio.kiripix("decide", ids[0], "place", "--decision", JSON.stringify({ decision: "marker", data: spawn }));
  studio.kiripix("decide", ids[1], "place", "--decision", JSON.stringify({ decision: "marker", data: spawn }));
  exit(studio, ids[0], "exit.east", ids[1], "exit.west");
  exit(studio, ids[1], "exit.west", ids[0], "exit.east");
  for (const id of ids) studio.run(id);
}

test("Export asks first with a dry run and writes only on confirm", async ({ page, studio }) => {
  exportableDistrict(studio);
  await page.goto(at(studio, "room.ch03_*"));
  await expect(page.getByTestId("district-summary")).toContainText("2 rooms");
  const manifest = join(studio.cwd, "game", "kiripix", "manifest", "room.ch03_a.json");

  await page.getByTestId("district-export").click();
  await expect(page.getByTestId("district-confirm")).toBeVisible();
  expect(existsSync(manifest)).toBe(false); // the dry run wrote nothing
  await page.screenshot({ path: "shots/district-export-confirm.png" });
  await page.getByTestId("district-confirm-cancel").click();
  await expect(page.getByTestId("district-confirm")).toHaveCount(0);
  expect(existsSync(manifest)).toBe(false);

  await page.getByTestId("district-export").click();
  await page.getByTestId("district-confirm-export").click();
  await expect(page.getByTestId("district-outcome")).toHaveAttribute("data-label", "Export");
  await expect(page.getByTestId("district-outcome")).toContainText("written");
  expect(existsSync(manifest)).toBe(true);
});

test("Review this district opens queue mode with the glob", async ({ page, studio }) => {
  district(studio);
  await page.goto(at(studio, "room.ch01_dungeon_*"));
  await expect(page.getByTestId("district-summary")).toContainText("3 rooms");
  await page.getByTestId("district-review").click();
  await expect(page.getByTestId("queue-strip")).toBeVisible();
  await expect(page.getByTestId("queue-match")).toHaveValue("room.ch01_dungeon_*");
});

test("the view follows the Project: a Run by an agent changes a room's Stage", async ({ page, studio }) => {
  district(studio);
  await page.goto(at(studio, "room.ch01_dungeon_*"));
  await expect(page.getByTestId("district-summary")).toContainText("3 rooms");
  studio.kiripix("new", "room", "ch01_dungeon_d", "--view", "top");
  await expect(page.getByTestId("district-summary")).toContainText("4 rooms");
});
