import { test, expect } from "@playwright/test";
test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

test("mobile character entry → profile + portrait → edit → refine → portrait versions → rehearsal", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/characters");
  await expect(page).toHaveURL(/rehearsal\?view=characters/);
  await expect(
    page.getByRole("heading", { name: /Every story.*starts with someone/ }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/mobile-character-library.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Create character", exact: true })
    .click();
  await page
    .getByLabel("Describe your character")
    .fill(
      "A quiet astronomer with silver hair and a dry wit, determined to save her observatory.",
    );
  await page
    .getByRole("button", { name: /^Create character/ })
    .last()
    .click();
  await expect(page.getByAltText("Portrait of Evelyn")).toBeVisible();
  const cc = await (await request.get("/api/creator/characters")).json();
  expect(cc).toHaveLength(1);
  expect(cc[0].current_image_id).toBeTruthy();
  await page.screenshot({
    path: "test-results/mobile-character-detail.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Edit character", exact: true })
    .click();
  const panel = page.getByRole("dialog");
  await panel.getByLabel("Name", { exact: true }).fill("Vera");
  await panel.getByLabel("What do they want?").fill("Save her observatory.");
  await panel
    .getByRole("button", { name: "Save character", exact: true })
    .click();
  await expect(panel).not.toBeVisible();
  await page
    .getByRole("button", { name: "Refine with AI", exact: true })
    .click();
  await panel
    .getByLabel("What should change?")
    .fill("Make her more distant without changing her appearance.");
  await panel
    .getByRole("button", { name: "Preview changes", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Apply these changes" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Apply these changes" }).click();
  await expect(panel).not.toBeVisible();
  await page.getByRole("button", { name: /Edit portrait/ }).click();
  await panel
    .getByLabel("What should change in the portrait?")
    .fill("Give her auburn hair. Keep the rest.");
  await panel
    .getByRole("button", { name: "Edit portrait", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Use this portrait" }),
  ).toHaveCount(1);
  await panel.getByRole("button", { name: "Use this portrait" }).click();
  await expect(
    panel.getByRole("button", { name: "Selected", exact: true }),
  ).toHaveCount(1);
  await panel.getByRole("button", { name: "Close panel" }).click();
  await page.getByRole("button", { name: /Rehearse with Vera/ }).click();
  await expect(page.getByRole("heading", { name: /Who is in/ })).toBeVisible();
  await expect(page.locator(".rh-cast-slot").first()).toContainText("Vera");
  expect(page.url()).toContain("/rehearsal");
  expect(errors).toEqual([]);
});


test("a slow portrait provider does not hold up the saved character profile", async ({ page, request }) => {
  const backend = "http://127.0.0.1:8001";
  await request.post(backend + "/__test/image-delay/true");
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/characters/new");
    await page.getByLabel("Describe your character")
      .fill("A gentle astronomer with long silver hair, clear blue eyes, and a warm smile.");
    await page.getByRole("button", { name: /^Create character/ }).last().click();

    // The image API is deliberately still blocked here.
    await expect(page.getByRole("heading", { name: "Evelyn" })).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".mc-portrait-pending[role=\"status\"]")).toContainText("Portrait generating in the background");
    const characters = await (await request.get(backend + "/api/creator/characters")).json();
    expect(characters).toHaveLength(1);
    expect(characters[0].profile.name).toBe("Evelyn");
    expect(characters[0].current_image_id).toBeNull();

    await request.post(backend + "/__test/image-delay/false");
    await expect(page.getByAltText("Portrait of Evelyn")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Portrait generating in the background")).toHaveCount(0);
    const saved = await (await request.get(backend + "/api/creator/characters")).json();
    expect(saved[0].current_image_id).toBeTruthy();
  } finally {
    await request.post(backend + "/__test/image-delay/false");
  }
});

test("portrait failure retains character; retry only the portrait", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:8001/__test/image-failure/true");
  await page.goto("/characters/new");
  await expect(page).toHaveURL(/rehearsal\?view=characters&create=1/);
  await page
    .getByLabel("Describe your character")
    .fill("An observant librarian with silver hair and a soft voice.");
  await page
    .getByRole("button", { name: /^Create character/ })
    .last()
    .click();
  await expect(
    page.getByRole("button", { name: "Retry portrait", exact: true }),
  ).toBeVisible();
  let cc = await (await request.get("/api/creator/characters")).json();
  expect(cc).toHaveLength(1);
  expect(cc[0].profile_version).toBe(1);
  expect(cc[0].current_image_id).toBeNull();
  await request.post("http://127.0.0.1:8001/__test/image-failure/false");
  await page
    .getByRole("button", { name: "Retry portrait", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("button", { name: "Selected", exact: true }),
  ).toBeVisible();
  cc = await (await request.get("/api/creator/characters")).json();
  expect(cc).toHaveLength(1);
  expect(cc[0].profile_version).toBe(1);
  expect(cc[0].current_image_id).toBeTruthy();
});

test("lost creation response recovers both profile and portrait after refresh", async ({
  page,
  request,
}) => {
  await page.goto("/characters/new");
  await page
    .getByLabel("Describe your character")
    .fill(
      "A quiet astronomer with silver hair and a deeply independent spirit.",
    );
  await page.route("**/api/creator/characters", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fetch();
    await route.abort("failed");
  });
  await page
    .getByRole("button", { name: /^Create character/ })
    .last()
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/creator/characters")).json()).length,
    )
    .toBe(1);
  await page.reload();
  await expect(page.getByAltText("Portrait of Evelyn")).toBeVisible();
  const cs = await (await request.get("/api/creator/characters")).json();
  expect(cs).toHaveLength(1);
  expect(cs[0].current_image_id).toBeTruthy();
  const portraits = await (
    await request.get(`/api/characters/${cs[0].id}/images`)
  ).json();
  expect(portraits).toHaveLength(1);
});



test("voice-enabled creation keeps portrait and voice selection in one creation view", async ({page}) => {
  await page.setViewportSize({width: 390,height:844});
  let selectedVoice: {provider:string;voice_id:string;name:string}|null=null;
  const choices=["a","b","c"].map((id,i)=>({provider:"elevenlabs",voice_id:id,name:"Voice "+id,preview_url:"https://example.com/sample.mp3",reason:"Fits the character",labels:{}}));
  await page.route("**/api/health",async route=>{
    const response=await route.fetch();
    await route.fulfill({response,json:{...await response.json(),voice_enabled:true}});
  });
  await page.route("**/api/voice/characters/**",async route=>{
    const req=route.request();
    if(req.url().endsWith("/recommend")){
      await route.fulfill({json:{reason:"ai",choices,profile_version:1,sample_text:"The stars have not forgotten us.",sample_id:"a".repeat(64)}});
    }else if(req.method()==="PUT"){
      const id=req.postDataJSON().voice_id;
      selectedVoice={provider:"elevenlabs",voice_id:id,name:"Voice "+id};
      await route.fulfill({json:{voice:selectedVoice}});
    }else{
      await route.fulfill({json:{enabled:true,preview_synthesis:true,voice:selectedVoice,profile_version:1}});
    }
  });
  await page.goto("/characters/new");
  await page.getByLabel("Describe your character").fill("A reserved astronomer with a quiet voice.");
  await page.getByRole("button",{name:/^Create character/}).last().click();
  await expect(page.getByRole("heading",{name:"Evelyn"})).toBeVisible();
  await expect(page).toHaveURL(/create=1.*character=/);
  await expect(page.getByLabel("Shared dialogue sample")).toContainText("The stars have not forgotten us.");
  const candidate=page.getByRole("button",{name:/ALTERNATIVE Voice b/});
  await candidate.click();
  await expect(candidate).toHaveAttribute("aria-pressed","true");
  const mark=candidate.locator("span[aria-hidden=true]");
  const bounds=await mark.boundingBox();
  expect(bounds?.width).toBeCloseTo(bounds?.height||0,0);
  await page.getByRole("button",{name:"Confirm voice"}).click();
  await expect(page.getByText("Saved voice")).toBeVisible();
  await page.getByRole("button",{name:"Finish character creation"}).click();
  await expect(page).not.toHaveURL(/create=1/);
  await expect(page.getByRole("button",{name:/Rehearse with Evelyn/})).toBeVisible();
});


test("failed portrait can be recovered from private Discover detail after reload", async ({page,request})=>{
  const backend="http://127.0.0.1:8001";
  await request.post(backend+"/__test/image-failure/true");
  try{
    await page.goto("/characters/new");
    await page.getByLabel("Describe your character").fill("A quiet wizard in black robes.");
    await page.getByRole("button",{name:/^Create character/}).last().click();
    await expect(page.getByRole("button",{name:"Retry portrait",exact:true})).toBeVisible();
    const cs=await (await request.get("/api/creator/characters")).json();
    expect(cs).toHaveLength(1);
    await page.goto("/marketplace/private/"+cs[0].id);
    await page.reload();
    await expect(page.getByRole("button",{name:"Retry portrait",exact:true})).toBeVisible();
    await request.post(backend+"/__test/image-failure/false");
    await page.getByRole("button",{name:"Retry portrait",exact:true}).click();
    await expect(page.getByAltText("Portrait of "+cs[0].profile.name)).toBeVisible();
    const after=await (await request.get("/api/creator/characters")).json();
    expect(after).toHaveLength(1);
    expect(after[0].profile_version).toBe(cs[0].profile_version);
    expect(after[0].current_image_id).toBeTruthy();
  }finally{await request.post(backend+"/__test/image-failure/false");}
});
