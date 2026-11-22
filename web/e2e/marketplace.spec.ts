import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("bookshop-style discovery shows sample covers, search and filter", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page).toHaveURL(/\/marketplace$/);
  await expect(page.getByRole("heading", { name: /Discover characters/ })).toBeVisible();
  await expect(page.locator(".em-app")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator(".em-filter.active")).toHaveCSS("background-color", "rgb(84, 64, 140)");
  await expect(page.getByRole("link", { name: /sample character Mira/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /sample character Leo/ })).toBeVisible();
  await expect(page.getByRole("img", { name: "Portrait of Mira" })).toHaveAttribute("src", "/portraits/mira.webp");
  await expect(page.getByRole("img", { name: "Portrait of Leo" })).toHaveAttribute("src", "/portraits/leo.webp");
  await expect(page.getByLabel("Artwork concept Vesper, not yet playable")).toBeVisible();
  await expect(page.getByLabel("Artwork concept Ren, not yet playable")).toBeVisible();
  await expect(page.getByLabel("Artwork concept Vesper, not yet playable").locator("img")).toHaveAttribute("src", "/portraits/red-horn.webp");
  await expect(page.getByLabel("Artwork concept Ren, not yet playable").locator("img")).toHaveAttribute("src", "/portraits/red-boy.webp");
  await expect.poll(async () => page.locator(".em-book-grid img").evaluateAll((imgs) => imgs.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".em-hero h1")).toHaveCSS("font-family", /Philosopher/);
  await expect(page.locator(".em-cover-title").first()).toHaveCSS("font-family", /Philosopher/);
  await expect(page.locator(".em-search input")).toHaveCSS("font-family", /Nunito Sans/);
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


test("owned published character appears once, opens public detail and supports listing management", async ({ page }) => {
  const backend = "http://127.0.0.1:8001";
  const created = await page.request.post(backend + "/api/rehearsal/characters", {
    data: {
      operation_id: crypto.randomUUID(),
      name: "Hazel",
      description: "A curious archivist with a private story.",
    },
  });
  expect(created.status()).toBe(201);
  const { character_id } = await created.json() as { character_id: string };

  // The first account claims pre-existing local characters.
  const signup = await page.request.post(backend + "/api/account/register", {
    data: { username: "hazelcreator", password: "test-password-12345" },
  });
  expect(signup.status()).toBe(200);
  const published = await page.request.post(backend + "/api/marketplace/listings", {
    data: {
      character_id,
      name: "Hazel",
      short_description: "A curious archivist.",
      tags: ["Mystery"],
      public_personality: ["Curious"],
      rights_basis: "original",
      rights_confirmed: true,
    },
  });
  expect(published.status()).toBe(200);
  const { listing_id } = await published.json() as { listing_id: string };

  await page.goto("/marketplace");
  const publicCard = page.getByRole("link", { name: "View published character Hazel" });
  await expect(publicCard).toBeVisible();
  await expect(page.locator(".em-book-card").filter({ hasText: "Hazel" })).toHaveCount(1);
  await publicCard.click();
  await expect(page).toHaveURL(new RegExp("/marketplace/" + listing_id));
  await expect(page.getByRole("heading", { name: "Hazel" })).toBeVisible();
  await expect(page.getByText("A curious archivist.", { exact: true })).toBeVisible();
  await expect(page.getByText("Personality")).toBeVisible();

  await page.goto("/characters/publish?character=" + encodeURIComponent(character_id));
  await expect(page.getByRole("heading", { name: "Manage listing" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save listing changes" })).toBeVisible();
  await expect(page.getByLabel("Public description")).toHaveValue("A curious archivist.");
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Unpublish listing" }).click();
  await expect(page.getByText(/Listing unpublished\. Your private character/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Republish to Marketplace" })).toBeVisible();
  const missing = await page.request.get(backend + "/api/marketplace/listings/" + listing_id);
  expect(missing.status()).toBe(404);

  await page.getByLabel("Public description").fill("A curious archivist returns.");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Republish to Marketplace" }).click();
  await expect(page.getByText("Listing saved successfully.")).toBeVisible();
  const restored = await page.request.get(backend + "/api/marketplace/listings/" + listing_id);
  expect(restored.status()).toBe(200);
  expect((await restored.json()).short_description).toBe("A curious archivist returns.");
});
