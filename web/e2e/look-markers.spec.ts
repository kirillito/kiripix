// Ticket 0317 (ADR 0013, spec §11): a Look's Markers on `place`, and `reach` and the walk test with a chosen Look, against a real
// `kiripix serve`.

import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, layeredRoom, png, test, type Studio } from "./harness";

const ROOM = "room.alley";
const LOOK = "gate_open";
const SHOTS = join(import.meta.dirname, "..", "test-results");
const GROUND = (x: number): [number, number, number, number] => (Math.floor(x / 2) < 24 ? [255, 0, 77, 255] : [29, 43, 83, 255]);

// The layered room (a lamp and a crate), with a wall of `solid` down x 26 to 30, and a Look `gate_open` with its own `solid` that
// erases that wall. The Spawn is left of the wall: the strip right of it (x 37 to 42 for the 12 x 8 Body) is an island of the room.
function roomWithAGate(studio: Studio, pick = true): void {
  layeredRoom(studio);
  for (const [layer, y] of [["crate", 17], ["lamp", 9]] as const) {
    const data = { id: `ysort.${layer}`, type: "ysort", x: 0, y, x2: 47, y2: y, layer };
    studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "marker", data }));
  }
  const decideMask = (name: string, data: object) =>
    studio.kiripix("decide", ROOM, "masks", "--decision", JSON.stringify({ decision: name, data }));
  decideMask("brush", { mask: "solid", erase: false, radius: 2, points: [[28, 0], [28, 31]] });
  const lamp = (x: number, y: number) => x >= 60 && x < 72 && y >= 8 && y < 20;
  studio.write("gate.png", png(96, 64, (x, y) => (lamp(x, y) ? [0, 0, 0, 255] : GROUND(x))));
  const variant = studio.json("import", ROOM, "incoming/gate.png", "--look", LOOK).data.variant as string;
  if (pick) studio.kiripix("pick", ROOM, variant, "--look", LOOK);
  const decideLook = (name: string, data: object) =>
    studio.kiripix("decide", ROOM, "looks", "--decision", JSON.stringify({ decision: name, data }));
  if (pick) {
    decideLook("polygon", { look: LOOK, points: [[28, 2], [38, 2], [38, 12], [28, 12]] });
    decideLook("solid", { look: LOOK, erase: true, radius: 3, points: [[28, 0], [28, 31]] });
  }
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "marker", data: { id: "spawn.main", type: "spawn", x: 16, y: 16 } }));
  studio.run(ROOM);
  studio.kiripix("run", ROOM, "reach");
}

async function open(page: Page, studio: Studio, stage: string): Promise<void> {
  await page.goto(studio.home);
  await page.getByTestId(`asset-${ROOM}`).click();
  await page.getByTestId(`stage-${stage}`).click();
  await expect(page.getByTestId("stage-title")).toHaveText(stage);
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");
}

function placed(studio: Studio): Record<string, unknown>[] {
  const stages = studio.json("show", ROOM).data.stages as { stage: string; decisions: { name: string; data: Record<string, unknown> }[] }[];
  return stages.find((entry) => entry.stage === "place")!.decisions.filter((entry) => entry.name === "marker").map((entry) => entry.data);
}

test("a light is given a Look on place: it shows with that Look chosen and hides without it", async ({ page, studio }) => {
  roomWithAGate(studio);
  studio.kiripix("decide", ROOM, "place", "--decision", JSON.stringify({ decision: "marker", data: { id: "light.1", type: "light", x: 30, y: 20, colour: "#ffffff", radius: 16, energy: 1 } }));
  studio.run(ROOM);
  await open(page, studio, "place");
  const canvas = page.getByTestId("canvas");
  await expect(canvas).toHaveAttribute("data-markers", /light\.1@30,20/);

  await page.getByTestId("marker-light.1").click();
  await page.getByTestId("marker-look").selectOption(LOOK);
  await page.getByTestId("marker-save").click();

  await expect.poll(() => placed(studio).filter((data) => data.id === "light.1").at(-1)).toMatchObject({ look: LOOK });
  await expect(page.getByTestId("place-look-view")).toHaveValue(LOOK); // chosen with the Look
  await expect(canvas).toHaveAttribute("data-markers", /light\.1@30,20/);
  await expect(page.getByTestId("marker-light.1")).toContainText(`in ${LOOK}`);
  await page.screenshot({ path: join(SHOTS, "look-markers-place-shown.png") });

  await page.getByTestId("place-look-view").selectOption("");
  await expect(canvas).not.toHaveAttribute("data-markers", /light\.1/);
  await expect(page.getByTestId("marker-light.1")).toHaveCount(0);
  await expect(canvas).toHaveAttribute("data-markers", /spawn\.main@16,16/); // the room's own stay
  await page.screenshot({ path: join(SHOTS, "look-markers-place-hidden.png") });

  await page.getByTestId("place-look-view").selectOption(LOOK);
  await expect(canvas).toHaveAttribute("data-markers", /light\.1@30,20/);
});

test("the Command's refusal of a Look with no pick shows as a finding", async ({ page, studio }) => {
  roomWithAGate(studio, false); // the edit is imported, not picked
  await open(page, studio, "place");
  await page.getByTestId("marker-type").selectOption("light");
  await page.getByTestId("marker-look").selectOption(LOOK);

  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  await page.mouse.click(box.x + left + 30.5 * zoom, box.y + top + 20.5 * zoom);

  await expect(page.getByText("marker.unknown_look").first()).toBeVisible();
  expect(placed(studio).filter((data) => data.id === "light.1")).toEqual([]);
});

test("reach with the Look chosen that erases a wall shows the yard reachable; without it, an island", async ({ page, studio }) => {
  roomWithAGate(studio);
  await open(page, studio, "reach");
  const canvas = page.getByTestId("canvas");

  await expect(page.getByTestId("reach-island")).toHaveCount(1); // the room alone: the yard behind the wall
  await expect(canvas).toHaveAttribute("data-reach-look", "");
  await expect(page.getByTestId("reach-island")).toContainText(`reached under ${LOOK}`);
  const island = (await canvas.getAttribute("data-reach-islands"))!;
  expect(island).not.toBe("");
  const roomSpots = Number(await canvas.getAttribute("data-reach-spots"));
  await page.screenshot({ path: join(SHOTS, "look-markers-reach-room.png") });

  await page.getByTestId("reach-look").selectOption(LOOK);

  await expect(canvas).toHaveAttribute("data-reach-look", LOOK);
  await expect(page.getByTestId("reach-no-islands")).toBeVisible();
  await expect(canvas).toHaveAttribute("data-reach-islands", "");
  await expect.poll(async () => Number(await canvas.getAttribute("data-reach-spots"))).toBeGreaterThan(roomSpots); // the yard is reached
  await page.screenshot({ path: join(SHOTS, "look-markers-reach-look.png") });

  await page.getByTestId("reach-look").selectOption("");
  await expect(page.getByTestId("reach-island")).toHaveCount(1);
});

test("the walk test with that Look chosen walks through the cleared opening; without it, the wall stops it", async ({ page, studio }) => {
  roomWithAGate(studio);
  await open(page, studio, "reach");
  const canvas = page.getByTestId("canvas");
  await page.getByTestId("walk-toggle").click();
  await expect(canvas).toHaveAttribute("data-body", "16,16");

  await page.keyboard.down("ArrowRight");
  await expect(canvas).toHaveAttribute("data-body", "20,16"); // walkable ends at x 20: the footprint touches the wall at x 26
  await page.waitForTimeout(400);
  await expect(canvas).toHaveAttribute("data-body", "20,16");
  await page.keyboard.up("ArrowRight");

  await page.getByTestId("reach-look").selectOption(LOOK);
  await expect(page.getByTestId("walk-toggle")).toHaveAttribute("aria-pressed", "true");
  await expect(canvas).toHaveAttribute("data-body", "20,16"); // the Body stays where it is
  await page.keyboard.down("ArrowRight");
  await expect(canvas).toHaveAttribute("data-body", /^(3\d|4[0-2]),16$/); // through where the wall was, into the yard
  await page.keyboard.up("ArrowRight");
  await page.screenshot({ path: join(SHOTS, "look-markers-walk-look.png") });
});
