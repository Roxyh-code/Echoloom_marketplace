import { test, expect } from "@playwright/test";
import { readCurrentSegment } from "./rehearsal-reader";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8001/__test/reset");
});

// The stage uses a decorative display face, which needs a larger pixel size
// than the story-reading face to remain legible in the shared mobile frame.
for (const viewport of [
  { width: 320, height: 740 },
  { width: 390, height: 844 },
  { width: 1024, height: 900 },
]) {
  test(`Story reader controls stay readable and unclipped at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.goto("/rehearsal");
    await page.locator(".rh-example").click();
    await page.getByRole("button", { name: /Start rehearsal/ }).click();
    await readCurrentSegment(page);

    const actions = page.locator(".rh-stage-actions > button");
    await expect(actions).toHaveCount(3);
    await expect(page.locator(".rh-action-label")).toHaveCount(2);

    const metrics = await page.evaluate(() => {
      const stage = document.querySelector<HTMLElement>(".rehearsal-app.rh-stage");
      const buttons = [...document.querySelectorAll<HTMLElement>(".rh-stage-actions > button")];
      const labels = [...document.querySelectorAll<HTMLElement>(".rh-stage-actions .rh-action-label")];
      const version = document.querySelector<HTMLElement>(".rh-version-link");
      const cast = document.querySelector<HTMLElement>(".rh-stage-context > button");
      const sync = document.querySelector<HTMLElement>(".rh-stage-context > .rh-sync");
      const segment = document.querySelector<HTMLElement>(".rh-segment > header");
      const progress = document.querySelector<HTMLElement>(".rh-line-progress");
      const size = (element: Element | null) =>
        element ? parseFloat(getComputedStyle(element).fontSize) : 0;
      if (!stage || buttons.length !== 3 || labels.length !== 2) {
        throw new Error("Story reader controls are missing");
      }
      const frame = stage.getBoundingClientRect();
      return {
        frameLeft: frame.left,
        frameRight: frame.right,
        horizontalOverflow: document.documentElement.scrollWidth - innerWidth,
        buttonSizes: buttons.map(size),
        buttonRects: buttons.map((b) => {
          const r = b.getBoundingClientRect();
          return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
        }),
        labelMeasurements: labels.map((el) => ({
          text: el.textContent,
          width: el.clientWidth,
          scrollWidth: el.scrollWidth,
          height: el.clientHeight,
          scrollHeight: el.scrollHeight,
        })),
        version: size(version),
        cast: size(cast),
        sync: size(sync),
        segment: size(segment),
        progress: size(progress),
        storySize: size(document.querySelector(".rh-block p")),
      };
    });

    const small = viewport.width <= 360;
    expect(metrics.buttonSizes[0]).toBeGreaterThanOrEqual(small ? 17 : 18);
    expect(metrics.buttonSizes[1]).toBeGreaterThanOrEqual(small ? 18 : 19);
    expect(metrics.buttonSizes[2]).toBeGreaterThanOrEqual(small ? 17 : 18);
    expect(metrics.version).toBeGreaterThanOrEqual(15);
    expect(metrics.cast).toBeGreaterThanOrEqual(14);
    expect(metrics.sync).toBeGreaterThanOrEqual(13);
    expect(metrics.segment).toBeGreaterThanOrEqual(13);
    expect(metrics.progress).toBeGreaterThanOrEqual(13);
    // The reading-size control still owns story prose; don't enlarge it by accident.
    expect(metrics.storySize).toBe(17);
    for (const label of metrics.labelMeasurements) {
      expect(label.scrollWidth, `${label.text} text overflows horizontally at ${viewport.width}px`).toBeLessThanOrEqual(label.width + 2);
      expect(label.scrollHeight, `${label.text} text is clipped vertically at ${viewport.width}px`).toBeLessThanOrEqual(label.height + 2);
    }
    expect(metrics.horizontalOverflow).toBeLessThanOrEqual(1);
    for (const button of metrics.buttonRects) {
      expect(button.left).toBeGreaterThanOrEqual(metrics.frameLeft - 1);
      expect(button.right).toBeLessThanOrEqual(metrics.frameRight + 1);
    }
    expect(metrics.buttonRects[0].right).toBeLessThanOrEqual(metrics.buttonRects[1].left + 1);
    expect(metrics.buttonRects[1].right).toBeLessThanOrEqual(metrics.buttonRects[2].left + 1);

    await page.screenshot({
      path: `test-results/editorial-story-typography-${viewport.width}.png`,
      fullPage: true,
    });
  });
}
