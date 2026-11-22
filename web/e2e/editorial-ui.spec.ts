import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("all story studio surfaces use original Bazar white and violet palette", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/rehearsal");
  await expect(page.getByRole("heading", { name: /Let your characters/ })).toBeVisible();
  await expect(page.locator(".rehearsal-app")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator(".rh-top")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator(".rh-primary").first()).toHaveCSS("background-color", "rgb(84, 64, 140)");
  await page.screenshot({ path: "test-results/editorial-story-library.png", fullPage: true });
  await page.getByRole("button", { name: /Rehearse a scene/ }).click();
  await expect(page.locator(".rh-cast-slot")).toHaveCount(2);
  await expect(page.locator(".rh-cast-slot").first()).toHaveCSS("background-color", "rgb(250, 250, 250)");
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
  await page.screenshot({ path: "test-results/editorial-character-library.png", fullPage: true });
  await page.locator(".mc-character-card").first().click();
  await expect(page.locator(".mc-character-cover")).toBeVisible();
  await expect(page.getByRole("button", { name: /Edit portrait/ })).toHaveCSS("color", "rgb(84, 64, 140)");
  await expect(page.locator(".mc-profile-body")).toBeVisible();
  await page.screenshot({ path: "test-results/editorial-character-detail.png", fullPage: true });
  await page.getByRole("button", { name: "Edit character", exact: true }).click();
  await expect(page.locator(".rh-sheet")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await page.screenshot({ path: "test-results/editorial-character-edit-sheet.png", fullPage: true });

  await page.goto("/rehearsal?view=characters&create=1");
  await expect(page.getByLabel("Describe your character")).toBeVisible();
  await page.screenshot({ path: "test-results/editorial-character-creation.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("story reader and intervention sheet use white Bazar surfaces", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/rehearsal");
  await page.locator(".rh-example").click();
  await page.getByRole("button", { name: /Start rehearsal/ }).click();
  await expect(page.locator(".rh-reading")).toBeVisible();
  await expect(page.locator(".rh-reading")).toHaveCSS("background-color", "rgb(250, 250, 250)");
  await page.screenshot({ path: "test-results/editorial-story-reader.png", fullPage: true });
  await page.getByRole("button", { name: "Intervene", exact: true }).click();
  await expect(page.locator(".rh-sheet")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await page.screenshot({ path: "test-results/editorial-story-intervention.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
