import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("bookshop-style discovery shows sample covers, search and filter", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page).toHaveURL(/\/marketplace$/);
  await expect(page.getByRole("heading", { name: /Discover characters/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /sample character Mira/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /sample character Leo/ })).toBeVisible();
  await page.screenshot({ path: "test-results/editorial-marketplace.png", fullPage: true });
  await page.getByRole("searchbox", { name: "Search characters" }).fill("Mira");
  await expect(page.getByRole("link", { name: /sample character Mira/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /sample character Leo/ })).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Search characters" }).fill("");
  await page.getByRole("button", { name: "My characters" }).click();
  await expect(page.getByText("Your shelf is waiting")).toBeVisible();
  await expect(page.getByRole("link", { name: /Create a character/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("select two private characters and carry them into an existing story draft", async ({ request, page }) => {
  for (const [name, description] of [
    ["Hazel", "An archivist who keeps the letters of an old kingdom."],
    ["Rowan", "A traveler returning after a promise was broken."],
  ]) {
    const response = await request.post("http://127.0.0.1:8001/api/rehearsal/characters", {
      data: { operation_id: crypto.randomUUID(), name, description },
    });
    expect(response.status()).toBe(201);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/marketplace");
  await expect(page.getByRole("button", { name: /Select Hazel for your cast/ })).toBeVisible();
  await page.getByRole("button", { name: /Select Hazel for your cast/ }).click();
  await page.getByRole("button", { name: /Select Rowan for your cast/ }).click();
  await expect(page.getByRole("button", { name: /Set the scene/ })).toBeEnabled();
  await page.getByRole("button", { name: /Set the scene/ }).click();
  await expect(page).toHaveURL(/\/rehearsal\?view=setup&scene=/);
  await expect(page.getByLabel("What situation are they in?", { exact: false })).toBeVisible();
  const scenes = await (await request.get("http://127.0.0.1:8001/api/rehearsal/scenes")).json();
  expect(scenes).toHaveLength(1);
  expect(scenes[0].document.cast).toHaveLength(2);
  expect(scenes[0].document.cast.map((c: {name:string}) => c.name).sort()).toEqual(["Hazel", "Rowan"]);
});
