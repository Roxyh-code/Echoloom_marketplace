import { test, expect } from "@playwright/test";
import { readCurrentSegment } from "./rehearsal-reader";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("Discovery shows unified placeholder character cards without separate artwork or story categories", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page).toHaveURL(/\/marketplace$/);
  await expect(page.getByRole("heading", { name: /Discover characters/ })).toBeVisible();
  await expect(page.getByText("Choose two characters. Imagine what happens when their worlds collide.")).toHaveCount(0);
  await expect(page.getByText("Marketplace preview.")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Open story studio/ })).toBeVisible();
  await expect(page.locator(".em-app")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await expect(page.locator(".em-filter.active")).toHaveCSS("background-color", "rgb(110, 82, 200)");
  await expect(page.getByRole("button", { name: "Art previews" })).toHaveCount(0);
  await expect(page.locator(".em-filters button")).toHaveCount(3);
  for (const [name, image] of [
    ["Mira", "/portraits/mira.webp"],
    ["Leo", "/portraits/leo.webp"],
    ["Vesper", "/portraits/red-horn.webp"],
    ["Ren", "/portraits/red-boy.webp"],
  ]) {
    const card = page.getByRole("link", { name: "View character " + name });
    await expect(card).toBeVisible();
    await expect(card.getByRole("img", { name: "Portrait of " + name })).toHaveAttribute("src", image);
  }
  await expect(page.locator(".em-cover-edition")).toHaveCount(0);
  await expect(page.locator(".em-cover-caption")).toHaveCount(0);
  await expect.poll(async () => page.locator(".em-book-grid img").evaluateAll((imgs) => imgs.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".em-hero h1")).toHaveCSS("font-family", /Pirata One/);
  await expect(page.locator(".em-cover-title").first()).toHaveCSS("font-family", /Grenze Gotisch/);
  await page.screenshot({ path: "test-results/editorial-marketplace.png", fullPage: true });
  await page.getByRole("searchbox", { name: "Search characters" }).fill("Mira");
  await expect(page.getByRole("link", { name: "View character Mira" })).toBeVisible();
  await expect(page.getByRole("link", { name: "View character Leo" })).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Search characters" }).fill("");
  await page.getByRole("link", { name: "View character Vesper" }).click();
  await expect(page).toHaveURL(/\/marketplace\/preview\/concept-vesper$/);
  await expect(page.getByRole("heading", { name: "Vesper" })).toBeVisible();
  await page.getByRole("link", { name: /Discover/ }).first().click();
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
  await expect(page.locator(".em-book-grid .em-book-card")).toHaveCount(4);
  await expect(page.getByRole("link", { name: "View character Ren" })).toHaveCount(0);
  await page.getByRole("button", { name: "Published", exact: true }).click();
  await expect(page.locator(".em-book-grid .em-book-card")).toHaveCount(1);
  await expect(page.getByRole("link", { name: "View character Mira" })).toHaveCount(0);
  await publicCard.click();
  await expect(page).toHaveURL(new RegExp("/marketplace/" + listing_id));
  await expect(page.getByRole("heading", { name: "Hazel" })).toBeVisible();
  await expect(page.getByText("Character preview.")).toHaveCount(0);
  await expect(page.getByText("A curious archivist.", { exact: true })).toBeVisible();
  await expect(page.getByText("Personality")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".em-detail-page")).toHaveCSS("background-color", "rgb(9, 10, 16)");
  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: "test-results/editorial-public-listing.png", fullPage: true });

  await page.goto("/characters/publish?character=" + encodeURIComponent(character_id));
  await expect(page.getByRole("heading", { name: "Manage listing" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save listing changes" })).toBeVisible();
  await expect(page.getByText("Future creator payouts")).toBeVisible();
  await expect(page.getByText(/Planned test pack:/)).toBeHidden();
  await expect(page.getByLabel("Public description")).toHaveValue("A curious archivist.");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "test-results/editorial-listing-management.png", fullPage: true });
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Unpublish listing" }).click();
  await expect(page.getByText(/Listing unpublished\. Your private character/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Republish to Marketplace" })).toBeVisible();
  const missing = await page.request.get(backend + "/api/marketplace/listings/" + listing_id);
  expect(missing.status()).toBe(404);

  await page.getByLabel("Public description").fill("A curious archivist returns.");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Republish to Marketplace" }).click();
  await expect(page.getByText("Listing saved.")).toBeVisible();
  const restored = await page.request.get(backend + "/api/marketplace/listings/" + listing_id);
  expect(restored.status()).toBe(200);
  expect((await restored.json()).short_description).toBe("A curious archivist returns.");
});

test("bottom navigation keeps the same order and column across pages, even on hover", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const labels = ["Discover", "Characters", "My stories"];
  const nav = page.getByRole("navigation", { name: "Primary navigation" });

  async function expectStableNavigation(active: string) {
    const tabs = nav.locator(":scope > a, :scope > button");
    await expect(tabs).toHaveCount(3);
    await expect.poll(async () => tabs.allTextContents()).toEqual(labels);
    await expect(nav.getByRole(active === "Characters" || active === "My stories" ? "button" : "link", { name: active, exact: true }))
      .toHaveAttribute("aria-current", "page");
    const centres = await tabs.evaluateAll((nodes) =>
      nodes.map((node) => {
        const item = node.getBoundingClientRect();
        const container = node.parentElement!.getBoundingClientRect();
        return (item.x + item.width / 2 - container.x) / container.width;
      })
    );
    for (const [i, x] of centres.entries()) {
      expect(x, `Tab ${labels[i]} must stay in column ${i + 1}`).toBeGreaterThan((i + 0.25) / 3);
      expect(x, `Tab ${labels[i]} must stay in column ${i + 1}`).toBeLessThan((i + 0.75) / 3);
    }
  }

  await page.goto("/marketplace");
  await expectStableNavigation("Discover");
  const charactersLink = nav.getByRole("link", { name: "Characters", exact: true });
  await charactersLink.hover();
  await charactersLink.click();
  await expect(page).toHaveURL(/\/rehearsal\?view=characters/);
  await expect(page.locator(".mc-character-grid")).toBeVisible();
  await expectStableNavigation("Characters");

  await nav.getByRole("button", { name: "My stories", exact: true }).hover();
  await nav.getByRole("button", { name: "My stories", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Let your characters/ })).toBeVisible();
  await expectStableNavigation("My stories");

  await nav.getByRole("link", { name: "Discover", exact: true }).click();
  await expect(page).toHaveURL(/\/marketplace$/);
  await expectStableNavigation("Discover");

  await page.getByRole("link", { name: "View character Mira" }).click();
  await expect(page).toHaveURL(/\/marketplace\/preview\/sample-mira/);
  await expectStableNavigation("Discover");
});


test("two published characters can be cast from Discover and detail, replaced, and loaded in Setup", async ({ page }) => {
  const backend = "http://127.0.0.1:8001";
  const characters: Record<string, string> = {};
  for (const [name, description] of [
    ["Hazel", "A curious archivist keeping a private notebook."],
    ["Rowan", "A navigator with a forgotten promise."],
    ["Vesper", "A traveler who knows a secret."],
  ]) {
    const created = await page.request.post(backend + "/api/rehearsal/characters", {
      data: { operation_id: crypto.randomUUID(), name, description },
    });
    expect(created.status()).toBe(201);
    characters[name] = (await created.json()).character_id;
  }
  const account = await page.request.post(backend + "/api/account/register", {
    data: { username: "castcreator", password: "test-password-12345" },
  });
  expect(account.status()).toBe(200);
  const listings: Record<string, string> = {};
  for (const name of ["Hazel", "Rowan", "Vesper"]) {
    const result = await page.request.post(backend + "/api/marketplace/listings", {
      data: {
        character_id: characters[name],
        name,
        short_description: "Published story persona of " + name,
        tags: ["Story"],
        public_personality: ["Curious"],
        rights_basis: "original",
        rights_confirmed: true,
      },
    });
    expect(result.status()).toBe(200);
    listings[name] = (await result.json()).listing_id;
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/marketplace");
  await page.getByRole("button", { name: "Select Hazel for your cast" }).click();
  await page.getByRole("link", { name: "View published character Rowan" }).click();
  await expect(page).toHaveURL(new RegExp("/marketplace/" + listings.Rowan));
  await page.getByRole("button", { name: "Add to story" }).click();
  await expect(page).toHaveURL(/\/marketplace$/);
  const tray = page.getByRole("complementary", { name: "Selected story cast" });
  await expect(tray).toContainText("Hazel");
  await expect(tray).toContainText("Rowan");

  // Replace slot A with a third published character, leaving slot B unchanged.
  await tray.getByRole("button", { name: "Replace Hazel" }).click();
  await page.getByRole("button", { name: "Select Vesper for your cast" }).click();
  await expect(tray).toContainText("Vesper");
  await expect(tray).not.toContainText("Hazel");
  await expect(tray).toContainText("Rowan");
  await page.reload();
  await expect(tray).toContainText("Vesper");

  await tray.getByRole("button", { name: /Set the scene/ }).click();
  await expect(page).toHaveURL(/\/rehearsal\?view=setup&scene=/);
  await expect(page.getByLabel("What situation are they in?", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Vesper" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rowan" })).toBeVisible();

  const scenes = await (await page.request.get(backend + "/api/rehearsal/scenes")).json();
  expect(scenes).toHaveLength(1);
  const scene = scenes[0];
  expect(scene.document.cast.map((actor: { name: string }) => actor.name)).toEqual(["Vesper", "Rowan"]);
  expect(scene.document.cast.map((actor: { source_listing_id: string }) => actor.source_listing_id)).toEqual([listings.Vesper, listings.Rowan]);
  expect(scene.document.cast.every((actor: { source_character_id: string | null }) => actor.source_character_id === null)).toBe(true);
  expect(scene.document.cast.every((actor: { profile: { backstory: string } }) => actor.profile.backstory === "")).toBe(true);

  // Scene API snapshots are authoritative even on a fresh page load.
  await page.goto("/rehearsal?view=cast&scene=" + encodeURIComponent(scene.id));
  await expect(page.getByText("Published characters are pinned to this scene.", { exact: false })).toBeVisible();
  await expect(page.getByText("Vesper", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Continue to scene setup/ }).click();
  await expect(page.getByLabel("What situation are they in?", { exact: false })).toBeVisible();
});

test("mixed published + private character casting uses two distinct authorized sources", async ({ page }) => {
  const backend = "http://127.0.0.1:8001";
  const seeds: Record<string, string> = {};
  for (const name of ["Published Hazel", "Private Jun"]) {
    const result = await page.request.post(backend + "/api/rehearsal/characters", {
      data: { operation_id: crypto.randomUUID(), name, description: "A character with a hidden history." },
    });
    expect(result.status()).toBe(201);
    seeds[name] = (await result.json()).character_id;
  }
  const registered = await page.request.post(backend + "/api/account/register", {
    data: { username: "mixedcast", password: "test-password-12345" },
  });
  expect(registered.status()).toBe(200);
  const listingResponse = await page.request.post(backend + "/api/marketplace/listings", {
    data: {
      character_id: seeds["Published Hazel"],
      name: "Published Hazel",
      short_description: "Public persona only.",
      tags: [],
      public_personality: ["Thoughtful"],
      rights_basis: "original",
      rights_confirmed: true,
    },
  });
  expect(listingResponse.status()).toBe(200);
  const listing = await listingResponse.json();
  await page.goto("/marketplace");
  await page.getByRole("button", { name: "Select Published Hazel for your cast" }).click();
  await page.getByRole("button", { name: "Select Private Jun for your cast" }).click();
  await page.getByRole("button", { name: /Set the scene/ }).click();
  await expect(page).toHaveURL(/\/rehearsal\?view=setup&scene=/);
  const scenes = await (await page.request.get(backend + "/api/rehearsal/scenes")).json();
  const actors = scenes[0].document.cast;
  expect(actors).toHaveLength(2);
  expect(actors[0].source_listing_id).toBe(listing.listing_id);
  expect(actors[0].source_character_id).toBeNull();
  expect(actors[1].source_character_id).toBe(seeds["Private Jun"]);
  const status = await page.request.get(backend + "/api/rehearsal/scenes/" + scenes[0].id + "/access");
  expect(status.status()).toBe(200);
  expect((await status.json()).mode).toBe("marketplace");
});


test("Marketplace → opening → free direction → locked AI → save and reopen", async ({ page }) => {
  const backend = "http://127.0.0.1:8001";
  const names = ["Mira", "Rowan"];
  const chars: string[] = [];
  for (const name of names) {
    const created = await page.request.post(backend + "/api/rehearsal/characters", {
      data: {
        operation_id: crypto.randomUUID(),
        name,
        description: name + " has a past they cannot easily discuss.",
      },
    });
    expect(created.status()).toBe(201);
    chars.push((await created.json()).character_id);
  }
  const account = await page.request.post(backend + "/api/account/register", {
    data: { username: "marketplacereader", password: "test-password-12345" },
  });
  expect(account.status()).toBe(200);
  const listingIds: string[] = [];
  for (const [index, name] of names.entries()) {
    const published = await page.request.post(backend + "/api/marketplace/listings", {
      data: {
        character_id: chars[index],
        name,
        short_description: name + " has a publicly told story.",
        tags: ["Drama"],
        public_personality: ["Determined"],
        rights_basis: "original",
        rights_confirmed: true,
      },
    });
    expect(published.status()).toBe(200);
    listingIds.push((await published.json()).listing_id);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/marketplace");
  for (const name of names) {
    await page.getByRole("button", { name: "Select " + name + " for your cast" }).click();
  }
  await page.getByRole("button", { name: /Set the scene/ }).click();
  await expect(page).toHaveURL(/\/rehearsal\?view=setup&scene=/);
  const scenesResponse = await page.request.get(backend + "/api/rehearsal/scenes");
  const scenes = await scenesResponse.json();
  expect(scenes).toHaveLength(1);
  const sid: string = scenes[0].id;
  expect(scenes[0].document.cast.map((a: { source_listing_id: string }) => a.source_listing_id)).toEqual(listingIds);
  const sceneAccessUrl = backend + "/api/rehearsal/scenes/" + sid + "/access";
  const accessBefore = await (await page.request.get(sceneAccessUrl)).json();
  expect(accessBefore.trial_eligible).toBe(true);
  await expect(page.getByRole("status", { name: "Story access" })).toContainText("Your free first story");
  await page.getByLabel("What situation are they in?", { exact: false })
    .fill("Mira and Rowan meet at the abandoned railway station after many years.");
  await page.getByRole("button", { name: /Start rehearsal/ }).click();
  await expect(page).toHaveURL(/\/rehearsal\?view=stage&scene=/);
  await readCurrentSegment(page);
  await expect(page.locator(".rh-segment").first()).toBeVisible();
  await expect(page.getByRole("status", { name: "Story access" })).toContainText("1 AI direction remaining");
  const afterOpening = await (await page.request.get(sceneAccessUrl)).json();
  expect(afterOpening.opening_consumed).toBe(true);
  expect(afterOpening.directions_available).toBe(1);

  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await readCurrentSegment(page);
  const afterDirection = await (await page.request.get(sceneAccessUrl)).json();
  expect(afterDirection.directions_available).toBe(0);
  expect(afterDirection.payment_required).toBe(true);
  const banner = page.getByRole("status", { name: "Story access" });
  await expect(banner).toContainText("Unlock required");
  await expect(banner).toContainText("Payments are not available");
  await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeDisabled();

  // Existing content remains readable after refresh and is never regenerated.
  const persisted = await (await page.request.get(backend + "/api/rehearsal/scenes/" + sid)).json();
  const existingNodeCount = Object.keys(persisted.document.nodes).length;
  expect(existingNodeCount).toBeGreaterThanOrEqual(2);
  await page.reload();
  await expect(page.locator(".rh-segment").first()).toBeVisible();
  await expect(page.getByRole("status", { name: "Story access" })).toContainText("Unlock required");
  const reopened = await (await page.request.get(backend + "/api/rehearsal/scenes/" + sid)).json();
  expect(Object.keys(reopened.document.nodes)).toHaveLength(existingNodeCount);

  // Reading and saving are always free, even after all AI directions are used.
  await page.getByRole("button", { name: "More options", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "End scene & review", exact: false }).click();
  await expect(page.getByRole("heading", { name: /A scene worth/ })).toBeVisible();
  await page.getByRole("button", { name: /Save this scene/ }).click();
  await expect(page.getByText("Saved as this scene’s result", { exact: false }).first()).toBeVisible();
  const saved = await (await page.request.get(backend + "/api/rehearsal/scenes/" + sid)).json();
  expect(saved.document.status).toBe("saved");
  expect(saved.document.result.head).toBeTruthy();
  await page.goto("/rehearsal");
  const card = page.locator(".rh-scene-card").filter({ hasText: "Mira & Rowan" });
  await expect(card).toBeVisible();
  await card.locator(".rh-card-open").click();
  await expect(page.getByRole("heading", { name: /A scene worth/ })).toBeVisible();
  await expect(page.getByText("Saved as this scene’s result", { exact: false }).first()).toBeVisible();
});

test("a second Marketplace Scene clearly requires a future unlock before AI generation", async ({ page }) => {
  const backend = "http://127.0.0.1:8001";
  const ids: string[] = [];
  for (const name of ["Rin", "Tao"]) {
    const created = await page.request.post(backend + "/api/rehearsal/characters", {
      data: { operation_id: crypto.randomUUID(), name, description: name + " remembers the station." },
    });
    expect(created.status()).toBe(201);
    ids.push((await created.json()).character_id);
  }
  expect((await page.request.post(backend + "/api/account/register", {
    data: { username: "secondreader", password: "test-password-12345" },
  })).status()).toBe(200);
  const listings = [];
  for (const [index, name] of ["Rin", "Tao"].entries()) {
    const result = await page.request.post(backend + "/api/marketplace/listings", {
      data: {
        character_id: ids[index], name, short_description: "Public role " + name,
        tags: [], public_personality: ["Calm"], rights_basis: "original", rights_confirmed: true,
      },
    });
    expect(result.status()).toBe(200);
    listings.push(await result.json());
  }
  const makeScene = async () => {
    const r = await page.request.post(backend + "/api/rehearsal/scenes", {
      data: {
        operation_id: crypto.randomUUID(),
        cast_sources: listings.map((l) => ({
          source: "listing", listing_id: l.listing_id, expected_revision: l.latest_revision,
        })),
        setup: { premise: "Two travelers meet at an unfamiliar station." },
      },
    });
    expect(r.status()).toBe(201);
    return r.json();
  };
  const first = await makeScene();
  const started = await page.request.post(backend + "/api/rehearsal/scenes/" + first.id + "/commands", {
    data: {
      operation_id: crypto.randomUUID(), expected_revision: first.revision, kind: "continue",
    },
  });
  expect(started.status()).toBe(200);
  const jid: string = (await started.json()).job_id;
  await expect.poll(async () => {
    const j = await page.request.get(backend + "/api/rehearsal/jobs/" + jid);
    return (await j.json()).status;
  }).toBe("completed");
  const second = await makeScene();
  await page.goto("/rehearsal?view=setup&scene=" + second.id);
  const banner = page.getByRole("status", { name: "Story access" });
  await expect(banner).toContainText("Unlock required");
  await expect(banner).toContainText("Payments are not available");
  await page.getByLabel("What situation are they in?", { exact: false })
    .fill("Another meeting at the station in the middle of a winter storm.");
  await expect(page.getByRole("button", { name: /Unlock required/ })).toBeDisabled();
  // A forged direct API request cannot bypass the front-end lock.
  const loaded = await (await page.request.get(backend + "/api/rehearsal/scenes/" + second.id)).json();
  const denied = await page.request.post(backend + "/api/rehearsal/scenes/" + second.id + "/commands", {
    data: { operation_id: crypto.randomUUID(), expected_revision: loaded.revision, kind: "continue" },
  });
  expect(denied.status()).toBe(402);
});
