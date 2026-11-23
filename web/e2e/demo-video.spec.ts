import { test, expect } from "@playwright/test";

// One-off visual walkthrough. Uses a temporary DB and scripted test AI.
// This test is never intended to merge into the product's main branch.
test.use({
  viewport: { width: 390, height: 844 },
  video: { mode: "on", size: { width: 390, height: 844 } },
});

test("record existing UI: create, edit, publish, revise, and cast", async ({ page }) => {
  test.setTimeout(180_000);
  const backend = "http://127.0.0.1:8001";
  const pause = async (ms = 1400) => page.waitForTimeout(ms);
  const title = "Kael Ashford";

  // Account + companion character are seeded before screen recording's UI flow.
  // These are temporary test records, not connected to anyone's actual account.
  const reset = await page.request.post(backend + "/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const reg = await page.request.post(backend + "/api/account/register", {
    data: { username: "echoloom_demo", password: "Demo_Only_2026_Test!" },
  });
  expect(reg.ok()).toBeTruthy();
  const buddy = await page.request.post(backend + "/api/rehearsal/characters", {
    data: {
      operation_id: crypto.randomUUID(),
      name: "Eira Morwen",
      description: "A loyal royal archivist who knows the secret routes beneath the city.",
    },
  });
  expect(buddy.status()).toBe(201);

  await page.goto("/marketplace");
  await expect(page.getByRole("heading", { name: /Discover characters/ })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await pause(2300);

  // Character Studio > Create character. The profile and portrait are
  // test-provider outputs; creation and storage are the real app workflow.
  await page.getByRole("link", { name: "Characters", exact: true }).click();
  await expect(page.locator(".mc-character-grid")).toBeVisible();
  await pause(1300);
  await page.getByRole("button", { name: "Create character", exact: true }).click();
  await expect(page.getByLabel("Describe your character")).toBeVisible();
  await pause(800);
  await page.getByLabel("Describe your character").fill(
    "A mysterious silver-haired young man in a tailored black suit. " +
    "He commands a secret underground organization in a gothic city. " +
    "Brilliant, reserved, fiercely protective, with a dry sense of humor."
  );
  await pause(2100);
  await page.getByRole("button", { name: /^Create character/ }).last().click();
  await expect(page.getByAltText("Portrait of " + title)).toBeVisible({ timeout: 30_000 });
  await pause(2600);

  // My Characters > character profile > direct editor.
  await page.getByRole("button", { name: "Edit character", exact: true }).click();
  const panel = page.getByRole("dialog");
  await expect(panel.getByLabel("Name", { exact: true })).toHaveValue(title);
  await pause(1500);
  await panel.getByLabel("What do they want?").fill(
    "Protect the hidden city's people and find the traitor in his inner circle."
  );
  await panel.getByLabel("Core traits").fill("Composed, Calculating, Loyal, Protective");
  await pause(900);
  await panel.getByRole("button", { name: "Save character", exact: true }).click();
  await expect(panel).not.toBeVisible();
  await pause(1500);

  // Character -> Publish: all rights confirmation and form validation are real.
  await page.getByRole("button", { name: /Publish to Marketplace/ }).click();
  await expect(page.getByRole("heading", { name: "Publish a character" })).toBeVisible();
  await pause(1700);
  await page.getByLabel("Public description").fill(
    "A silver-haired leader of a secret underground network. His loyalty has a price."
  );
  await page.getByLabel("Tags (comma-separated, maximum 8)").fill(
    "Dark Fantasy, Mystery, Romance"
  );
  await page.getByLabel("Public personality traits (comma-separated, maximum 6)").fill(
    "Composed, Protective, Loyal"
  );
  await pause(1600);
  await page.getByRole("checkbox").check();
  await pause(650);
  await page.getByRole("button", { name: "Publish to Marketplace" }).click();
  await expect(page.getByText("Published.", { exact: false })).toBeVisible();
  await pause(2200);

  // Real public listing and discovery: no entitlement bypass.
  await page.getByRole("link", { name: /View public listing/ }).first().click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await pause(2200);
  await page.getByRole("link", { name: "Echoloom Discover home" }).click();
  await page.getByRole("button", { name: "Published", exact: true }).click();
  await expect(page.getByRole("link", { name: "View published character " + title })).toBeVisible();
  await pause(2200);

  // Return to own character to update an existing public Listing revision.
  await page.getByRole("link", { name: "Characters", exact: true }).click();
  await expect(page.locator(".mc-character-grid")).toBeVisible();
  await page.locator(".mc-character-card").filter({ hasText: title }).click();
  await expect(page.getByRole("button", { name: /Manage Listing/ })).toBeVisible();
  await pause(950);
  await page.getByRole("button", { name: /Manage Listing/ }).click();
  await expect(page.getByRole("heading", { name: "Manage listing" })).toBeVisible();
  await pause(1200);
  await page.getByLabel("Public description").fill(
    "A silver-haired leader torn between duty and devotion. The secret he guards could change two lives."
  );
  await page.getByRole("checkbox").check();
  await pause(850);
  await page.getByRole("button", { name: "Save listing changes" }).click();
  await expect(page.getByText("Listing saved.", { exact: false })).toBeVisible();
  await pause(1800);

  // My Stories: existing *private-character* casting flow only. The future
  // public Marketplace paid-casting flow is NOT represented as implemented.
  await page.getByRole("link", { name: "← Marketplace" }).click();
  await page.getByRole("link", { name: "My stories", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Let your characters/ })).toBeVisible();
  await pause(2000);
  await page.getByRole("button", { name: /Rehearse a scene/ }).click();
  await expect(page.getByRole("heading", { name: /Who is in/ })).toBeVisible();
  await pause(1200);
  await page.locator(".rh-character-pick").filter({ hasText: title }).click();
  await pause(900);
  await page.locator(".rh-character-pick").filter({ hasText: "Eira Morwen" }).click();
  await pause(1500);
  await page.getByRole("button", { name: /Next: set the scene/ }).click();
  await expect(page.getByLabel("What situation are they in?", { exact: false })).toBeVisible();
  await pause(1100);
  await page.getByLabel("What situation are they in?", { exact: false }).fill(
    "On a moonlit rooftop, Kael and Eira uncover a letter that names a traitor within their circle."
  );
  await pause(3500);
  const video = page.video();
  await page.close();
  if (video) await video.saveAs("test-results/Echoloom_Character_Demo.webm");
});
