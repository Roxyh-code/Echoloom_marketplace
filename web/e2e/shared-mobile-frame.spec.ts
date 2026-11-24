import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

for (const viewport of [{ width: 390, height: 844 }, { width: 1024, height: 900 }]) {
  test(`Discover, Characters and My Stories share one phone frame at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/marketplace");
    const frame = page.locator(".el-mobile-frame");
    await expect(frame).toBeVisible();
    await expect(page.getByRole("heading", { name: "Discover characters" })).toBeVisible();

    const geometry = async () => {
      const rect = await frame.boundingBox();
      const nav = await page.getByRole("navigation", { name: "Primary navigation" }).boundingBox();
      expect(rect).not.toBeNull();
      expect(nav).not.toBeNull();
      return {
        left: rect!.x,
        top: rect!.y,
        width: rect!.width,
        height: rect!.height,
        navY: nav!.y,
        navHeight: nav!.height,
      };
    };
    const discover = await geometry();
    const assertSameFrame = (actual: Awaited<ReturnType<typeof geometry>>) => {
      for (const key of Object.keys(discover) as (keyof typeof discover)[]) {
        expect(Math.abs(actual[key] - discover[key]), `${key} changed on tab switch`).toBeLessThan(2);
      }
    };

    // A tall Discover catalog must scroll inside the shared frame.
    const catalog = page.locator(".em-page");
    await catalog.evaluate((element) => { element.scrollTop = 500; });
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
    assertSameFrame(await geometry());

    await page.getByRole("navigation", { name: "Primary navigation" })
      .getByRole("link", { name: "Characters" }).click();
    await expect(page.locator(".rehearsal-app.rh-characters")).toBeVisible();
    assertSameFrame(await geometry());

    await page.getByRole("navigation", { name: "Primary navigation" })
      .getByRole("button", { name: "My stories" }).click();
    await expect(page.locator(".rehearsal-app.rh-list")).toBeVisible();
    assertSameFrame(await geometry());

    await page.getByRole("navigation", { name: "Primary navigation" })
      .getByRole("link", { name: "Discover" }).click();
    await expect(page.locator(".em-app")).toBeVisible();
    assertSameFrame(await geometry());
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
  });
}
