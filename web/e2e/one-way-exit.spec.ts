// The flows of ticket 0365 (spec §6.1, §11): a one-way Exit from the place screen, and its arrow in the district view.

import { art, expect, test } from "./harness";

test("checking One-way records one Decision with one_way, and the district view draws one head", async ({ page, studio }) => {
  for (const name of ["a", "b"]) {
    const id = `room.ow_${name}`;
    studio.kiripix("new", "room", `ow_${name}`, "--view", "top");
    studio.kiripix("set", id, "brief", "width=48", "height=32");
    studio.kiripix("set", id, "fit", "scale=2");
    studio.kiripix("pick", id, studio.importVariant(id, `${name}.png`, art(24)));
    studio.run(id);
  }
  const back = { id: "exit.back", type: "exit", x: 5, y: 5, target_room: "room.ow_a", target_exit: "exit.pit" };
  studio.kiripix("decide", "room.ow_b", "place", "--decision", JSON.stringify({ decision: "marker", data: { ...back, target_exit: "exit.elsewhere" } }));

  await page.goto(studio.home);
  await page.getByTestId("asset-room.ow_a").click();
  await page.getByTestId("stage-place").click();
  await expect(page.getByTestId("canvas")).toHaveAttribute("data-loaded", "48x32");

  await page.getByTestId("marker-type").selectOption("exit");
  await page.getByTestId("marker-id").fill("exit.pit");
  await page.getByTestId("marker-target-room").selectOption("room.ow_b");
  await page.getByTestId("marker-target-exit").fill("exit.back");
  await page.getByTestId("marker-one-way").check();
  const canvas = page.getByTestId("canvas");
  const box = (await canvas.boundingBox())!;
  const zoom = Number(await canvas.getAttribute("data-zoom"));
  const [left, top] = (await canvas.getAttribute("data-origin"))!.split(",").map(Number);
  await page.mouse.click(box.x + left + 30.5 * zoom, box.y + top + 16.5 * zoom);
  await expect(page.getByTestId("decision-count")).toHaveText("1 Decision(s)");

  const stages = studio.json("show", "room.ow_a").data.stages as { stage: string; decisions: { data: Record<string, unknown> }[] }[];
  const decisions = stages.find((entry) => entry.stage === "place")!.decisions.map((decision) => decision.data);
  expect(decisions).toEqual([
    { id: "exit.pit", type: "exit", x: 30, y: 16, target_room: "room.ow_b", target_exit: "exit.back", one_way: true },
  ]);

  await page.goto(`${studio.url}?district=${encodeURIComponent("room.ow_*")}#${studio.home.split("#")[1]}`);
  const entry = page.getByTestId("district-exit-room.ow_a-exit.pit");
  await expect(entry).toHaveAttribute("data-pairing", "one_way");
  await expect(entry).toHaveAttribute("data-heads", "1");
  await expect(entry).toContainText("→");
  await page.screenshot({ path: "shots/district-one-way.png" });
});
