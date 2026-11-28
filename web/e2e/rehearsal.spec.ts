import { test, expect } from "@playwright/test";
import { readCurrentSegment } from "./rehearsal-reader";
test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("English mobile rehearsal → takeover → event → branch → save result → next scene", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/rehearsal");
  await expect(
    page.getByRole("heading", { name: /Let your characters/ }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/rehearsal-home.png",
    fullPage: true,
  });
  await page.locator(".rh-example").click();
  await page.screenshot({ path: "test-results/editorial-story-setup.png", fullPage: true });
  await page.getByRole("button", { name: /Start rehearsal/ }).click();
  await readCurrentSegment(page);
  await expect(
    page.getByText("I remembered how you take it.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Continue", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Intervene", exact: true }).click();
  let panel = page.getByRole("dialog");
  await panel.getByRole("button", { name: /Play a character/ }).click();
  await panel.getByRole("button", { name: /Lin.*Play this role/ }).click();
  await page
    .getByRole("textbox", { name: "Your performance" })
    .fill("Some things, you do remember.");
  await page.getByRole("button", { name: "Send performance" }).click();
  await readCurrentSegment(page);
  await expect(
    page.getByText("Some things, you do remember.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Hand back role", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Hand back role", exact: true })
    .click();
  await page.getByRole("button", { name: "Intervene", exact: true }).click();
  await panel.getByRole("button", { name: /Introduce an event/ }).click();
  await panel
    .getByLabel("What happens?", { exact: true })
    .fill("The departure announcement interrupts them.");
  await panel.getByRole("button", { name: /Add event/ }).click();
  await readCurrentSegment(page);
  await expect(
    page.getByRole("button", { name: "Continue", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Other directions", exact: true })
    .click();
  await expect(
    panel.getByRole("heading", { name: "A partial confession" }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/editorial-story-directions.png", fullPage: true });
  await page.screenshot({
    path: "test-results/rehearsal-directions.png",
    fullPage: true,
  });
  await panel.getByRole("button", { name: /A partial confession/ }).click();
  await readCurrentSegment(page);
  await expect(
    page.getByText(
      "I told them where you would be. I should have told you myself.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/rehearsal-stage.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "More options", exact: true }).click();
  await panel.getByRole("button", { name: /Versions/, exact: true }).click();
  const versions = panel.locator(".rh-version-list article");
  await expect(versions).toHaveCount(2);
  await versions.first().locator("button").first().click();
  await expect(
    page.getByText(
      "I told them where you would be. I should have told you myself.",
      { exact: true },
    ),
  ).not.toBeVisible();
  await page.getByRole("button", { name: /Version 1/ }).click();
  await panel
    .locator(".rh-version-list article")
    .last()
    .locator("button")
    .first()
    .click();
  await page.getByRole("button", { name: "More options", exact: true }).click();
  await panel
    .getByRole("button", { name: "End scene & review", exact: false })
    .click();
  await expect(
    page.getByRole("heading", { name: /A scene worth/ }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/editorial-story-review.png", fullPage: true });
  await page.getByRole("button", { name: /Save this scene/ }).click();
  await expect(
    page.getByText("Saved as this scene’s result", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Export scene", exact: true }).click();
  await panel
    .getByRole("button", { name: "Preview export", exact: true })
    .click();
  await expect(panel.locator("pre")).toContainText("I told them");
  const download = page.waitForEvent("download");
  await panel.getByRole("button", { name: /Download TXT/ }).click();
  expect((await download).suggestedFilename()).toMatch(/\.txt$/);
  await panel.getByRole("button", { name: "Close panel" }).click();
  await page.getByRole("button", { name: /Rehearse the next scene/ }).click();
  await expect(
    page.getByText("Continuing from", { exact: false }),
  ).toBeVisible();
  const ss = await (await request.get("/api/rehearsal/scenes")).json();
  expect(ss).toHaveLength(2);
  expect(
    ss.find((s: any) => !!s.document.source).document.initial_state.world_facts,
  ).not.toHaveLength(0);
  expect(errors).toEqual([]);
});

test("in-scene creation includes portraits, preserves cast and setup at 320px", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/rehearsal");
  await page
    .getByRole("button", { name: "Rehearse a scene", exact: false })
    .click();
  await expect(page.getByRole("heading", { name: /Who is in/ })).toBeVisible();
  const panel = page.getByRole("dialog");
  for (const [index, [name, description]] of [
    ["Lena", "A quiet restorer who wants an honest answer."],
    ["Rowan", "An old friend hiding why he left the city."],
  ].entries()) {
    await page
      .getByRole("button", { name: "Create", exact: false })
      .filter({ hasText: /Create/ })
      .first()
      .click();
    await page.getByLabel("Describe your character").fill(description);
    await expect(page.getByLabel("Describe your character")).toHaveValue(description);
    // At 320px the footer can animate while Playwright checks stability.
    // Force the REAL submit button click (not requestSubmit) so React has
    // committed the controlled textarea value before the form submits.
    await page.locator('button[form="mc-create"]').click({ force: true });
    // Distinguish server-side creation failures from a slow UI transition.
    await expect.poll(async () => {
      const items = await (await request.get("/api/creator/characters")).json();
      return items.length;
    }, { timeout: 15_000 }).toBe(index + 1);
    // The Profile is usable immediately. Do not require the portrait
    // to finish before editing or adding this Character to a Scene.
    try {
      await expect(page.getByRole("heading", { name: "Evelyn" })).toBeVisible({
        timeout: 15_000,
      });
    } catch (error) {
      // Test-only diagnostics: no private users or live model credentials.
      console.log("in-scene creation navigation", {
        index,
        url: page.url(),
        visibleText: (await page.locator("body").innerText()).slice(0, 1000),
      });
      throw error;
    }
    await page
      .getByRole("button", { name: "Edit character", exact: true })
      .click();
    await panel.getByLabel("Name", { exact: true }).fill(name);
    await panel
      .getByRole("button", { name: "Save character", exact: true })
      .click();
    await page.getByRole("button", { name: /Use in this scene/ }).click();
    await expect(
      page.getByRole("heading", { name: /Who is in/ }),
    ).toBeVisible();
  }
  await page.getByRole("button", { name: /Next: set the scene/ }).click();
  await page
    .getByLabel("What situation are they in?", { exact: false })
    .fill("They meet at a station on the evening before the gallery opens.");
  await expect(page.locator(".rh-sync").last()).toHaveText(
    "Saved automatically",
  );
  await page.reload();
  await expect(
    page.getByLabel("What situation are they in?", { exact: false }),
  ).toHaveValue(
    "They meet at a station on the evening before the gallery opens.",
  );
  await page.getByRole("button", { name: /Start rehearsal/ }).click();
  await readCurrentSegment(page);
  await expect(
    page.getByText("I hoped we would have a moment to talk.", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  const cc = await (await request.get("/api/rehearsal/characters")).json();
  expect(cc).toHaveLength(2);
  await expect.poll(async () => {
    const characters = await (await request.get("/api/rehearsal/characters")).json();
    return characters.every((c: any) => !!c.current_image_id);
  }, { timeout: 15_000 }).toBeTruthy();
});

test("permission denial never falls back to cached scene text", async ({
  page,
  request,
}) => {
  const created = await (
    await request.post("/api/rehearsal/scenes", {
      data: {
        operation_id: crypto.randomUUID(),
        demo: true,
        setup: { premise: "A private scene with a confidential premise." },
      },
    })
  ).json();
  await page.goto(`/rehearsal?view=stage&scene=${created.id}`);
  await expect(
    page.getByText("A private scene with a confidential premise.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.route(`**/api/rehearsal/scenes/${created.id}`, (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Scene not found." }),
    }),
  );
  await page.reload();
  await expect(page.locator(".rh-alert[role=alert]")).toContainText(
    "Scene not found.",
  );
  await expect(
    page.getByText("A private scene with a confidential premise.", {
      exact: true,
    }),
  ).not.toBeVisible();
});

test("one paragraph at a time → refresh preserves complete passage and unseen future", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/rehearsal");
  await page.locator(".rh-example").click();
  await page.getByRole("button", { name: /Start rehearsal/ }).click();
  await expect(page.locator(".rehearsal-app")).toHaveAttribute(
    "data-generating",
    "false",
  );
  await expect(
    page.getByText(
      "Rain softens the station lights. Two cups of coffee wait on the bench.",
      { exact: true },
    ),
  ).toBeVisible();
  // Both descriptive sentences are a single narration paragraph.
  await expect(
    page.getByText("He pushes the warm cup a little closer.", { exact: true }),
  ).not.toBeVisible();
  await expect(
    page.getByText("I remembered how you take it.", { exact: true }),
  ).not.toBeVisible();
  const initial = await (await request.get("/api/rehearsal/scenes")).json();
  const sid = initial[0].id;
  const original = initial[0].document.active_version;
  const originalHead = initial[0].document.versions[original].head;
  const originalNodes = Object.keys(initial[0].document.nodes).length;
  await page.getByRole("button", { name: "Next paragraph", exact: true }).click();
  await expect(
    page.getByText("He pushes the warm cup a little closer.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("I remembered how you take it.", { exact: true }),
  ).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByText("He pushes the warm cup a little closer.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("I remembered how you take it.", { exact: true }),
  ).not.toBeVisible();
  const read = await (await request.get(`/api/rehearsal/scenes/${sid}`)).json();
  expect(Object.keys(read.document.nodes)).toHaveLength(originalNodes);
  expect(read.document.versions[original].head).toBe(originalHead);
  await page.getByRole("button", { name: "Intervene", exact: true }).click();
  const panel = page.getByRole("dialog");
  await panel.getByRole("button", { name: /Play a character/ }).click();
  await panel.getByRole("button", { name: /Lin.*Play this role/ }).click();
  const changed = await (
    await request.get(`/api/rehearsal/scenes/${sid}`)
  ).json();
  expect(changed.document.active_version).not.toBe(original);
  const head =
    changed.document.nodes[
      changed.document.versions[changed.document.active_version].head
    ];
  expect(head.blocks.map((b: any) => b.text).join("")).toBe(
    "Rain softens the station lights. Two cups of coffee wait on the bench." +
    "He pushes the warm cup a little closer.",
  );
  expect(changed.document.versions[original].head).toBe(originalHead);
  await page.screenshot({
    path: "test-results/rehearsal-paced-reading.png",
    fullPage: true,
  });
});


test("inline audio controls request only the selected revealed passage", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  // Inject voice identities only into deterministic fixture responses, never the database.
  await page.route("**/api/rehearsal/**", async route=>{
    if(route.request().url().includes("/audio")){await route.continue();return;}
    const response=await route.fetch();
    const type=response.headers()["content-type"]||"";
    if(!type.includes("application/json")){await route.fulfill({response});return;}
    const data=await response.json();
    function addVoices(value:any){
      if(!value||typeof value!=="object")return;
      if(Array.isArray(value)){value.forEach(addVoices);return;}
      if(value.document&&Array.isArray(value.document.cast)){
        value.document.cast.forEach((actor:any,i:number)=>{actor.voice_identity={provider:"elevenlabs",voice_id:"demo-"+i,name:"Voice "+i};});
      }
      Object.values(value).forEach(addVoices);
    }
    addVoices(data);
    await route.fulfill({response,json:data});
  });
  await page.route("**/api/voice/audio/status",route=>route.fulfill({json:{enabled:true,narration:true}}));
  const requests:any[]=[];
  await page.route("**/api/voice/scenes/*/audio",async route=>{
    requests.push(route.request().postDataJSON());
    await route.fulfill({status:503,json:{detail:"Test audio unavailable."}});
  });
  await page.goto("/rehearsal");
  await page.locator(".rh-example").click();
  await page.getByRole("button",{name:/Start rehearsal/}).click();
  await readCurrentSegment(page);
  const dialogue=page.locator(".rh-block.dialogue").first();
  const narrator=page.locator(".rh-block.narration").first();
  const dialogueButton=dialogue.getByRole("button",{name:/Play audio for/});
  const narrationButton=narrator.getByRole("button",{name:"Play audio for narration"});
  await expect(dialogueButton).toBeVisible();
  await expect(narrationButton).toBeVisible();
  await expect(page.getByRole("button",{name:/Listen to story/})).toHaveCount(0);
  expect(requests).toHaveLength(0);
  const blockId=await dialogueButton.getAttribute("data-audio-block");
  await dialogueButton.click();
  await expect(dialogue.getByRole("alert")).toContainText("Test audio unavailable.");
  expect(requests).toHaveLength(1);
  expect(requests[0].block_id).toBe(blockId);
  expect(Object.keys(requests[0]).sort()).toEqual(["block_id","node_id","version_id"]);
  await expect(dialogue.getByRole("button",{name:/Paragraph options/})).toBeVisible();
  const narrationId=await narrationButton.getAttribute("data-audio-block");
  await narrationButton.click();
  await expect(narrator.getByRole("alert")).toContainText("Test audio unavailable.");
  expect(requests).toHaveLength(2);
  expect(requests[1].block_id).toBe(narrationId);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
