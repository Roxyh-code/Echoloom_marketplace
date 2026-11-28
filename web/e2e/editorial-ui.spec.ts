import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("story studio surfaces use dark fantasy and Moonlit Violet palette", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/rehearsal");
  await expect(page.getByRole("heading", { name: /Let your characters/ })).toBeVisible();
  await expect(page.locator(".rehearsal-app")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await expect(page.locator(".rh-top")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await expect(page.locator(".rh-primary").first()).toHaveCSS("background-color", "rgb(110, 82, 200)");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-story-library.png", fullPage: true });
  await page.getByRole("button", { name: /Rehearse a scene/ }).click();
  await expect(page.locator(".rh-cast-slot")).toHaveCount(2);
  await expect(page.locator(".rh-cast-slot").first()).toHaveCSS("background-color", "rgb(20, 19, 30)");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-cast.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("character library, creation form, detail profile and edit sheet all match theme", async ({ page, request }) => {
  const r = await request.post("http://127.0.0.1:8001/api/rehearsal/characters", {
    data: { operation_id: crypto.randomUUID(), name: "Hazel", description: "A scholar with a library of lost stories." },
  });
  expect(r.status()).toBe(201);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/rehearsal?view=characters");
  await expect(page.locator(".mc-character-grid")).toBeVisible();
  await expect(page.locator(".mc-character-card")).toHaveCount(1);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-character-library.png", fullPage: true });
  await page.locator(".mc-character-card").first().click();
  await expect(page.locator(".mc-character-cover")).toBeVisible();
  await expect(page.getByRole("button", { name: /Edit portrait/ })).toHaveCSS("color", "rgb(207, 186, 255)");
  await expect(page.locator(".mc-profile-body")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-character-detail.png", fullPage: true });
  await page.getByRole("button", { name: "Edit character", exact: true }).click();
  await expect(page.locator(".rh-sheet")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-character-edit-sheet.png", fullPage: true });

  await page.goto("/rehearsal?view=characters&create=1");
  await expect(page.getByLabel("Describe your character")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-character-creation.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("story reader and intervention sheet use the dark fantasy palette", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/rehearsal");
  await page.locator(".rh-example").click();
  await page.getByRole("button", { name: /Start rehearsal/ }).click();
  await expect(page.locator(".rh-reading")).toBeVisible();
  await expect(page.locator(".rh-reading")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-story-reader.png", fullPage: true });
  await page.getByRole("button", { name: "Intervene", exact: true }).click();
  await expect(page.locator(".rh-sheet")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-story-intervention.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});


test("capture research-enabled creation and reviewable research update", async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  // UI fixtures only: no real Firecrawl request or external source is asserted.
  await page.route("**/api/health",async route=>{
    const response=await route.fetch();
    await route.fulfill({response,json:{...await response.json(),research_enabled:true}});
  });
  await page.goto("/rehearsal?view=characters&create=1");
  await expect(page.getByRole("switch",{name:"Research character"})).toBeChecked();
  await page.getByLabel("Describe your character").fill("An astronomer from the fictional world of Starfall.");
  await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:"test-results/editorial-research-create.png",fullPage:false});
  const response=await page.request.post("http://127.0.0.1:8001/api/creator/characters",{
    data:{request_id:crypto.randomUUID(),description:"A reserved astronomer with silver hair."}
  });
  expect(response.status()).toBe(201);
  const cid=(await response.json()).character_id;
  await page.route("**/api/characters/"+cid,async route=>{
    const r=await route.fetch();
    const c=await r.json();
    await route.fulfill({response:r,json:{...c,research:{
      status:"proposal",base_version:c.profile_version,
      sources:["https://example.com/starfall/characters","https://example.com/starfall/lore"],
      proposal:{...c.profile,short_description:"A reserved astronomer who records forgotten constellations.",backstory:"In this fictional demo, she guards the observatory's lost star charts.",personality:{...c.profile.personality,core_traits:["Observant","Patient","Reserved"]}}
    }}});
  });
  await page.goto("/rehearsal?view=characters&character="+cid);
  await expect(page.getByText("Research update ready")).toBeVisible();
  await page.getByText("Research sources · 2 · Firecrawl",{exact:true}).click();
  await expect(page.getByText("Proposed profile",{exact:true})).toBeVisible();
  await page.getByText("Research update ready").evaluate(el=>el.scrollIntoView({block:"start"}));
  await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:"test-results/editorial-research-update.png",fullPage:false});
});
