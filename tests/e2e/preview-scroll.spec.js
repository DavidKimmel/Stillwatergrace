const { test, expect } = require('@playwright/test');

test('open detail panel and scroll to find video player', async ({ page }) => {
  test.setTimeout(30000);

  await page.goto('http://localhost:5175');
  await page.waitForLoadState('networkidle');

  // Click content card
  const card = page.locator('text=Psa').first();
  await card.click();
  await page.waitForTimeout(1500);

  // The panel is open. Let's scroll within it to find video
  // First take screenshot of top
  await page.screenshot({ path: 'tests/e2e/screenshots/scroll-01-top.png', fullPage: true });

  // Scroll down in the panel
  const panel = page.locator('[class*="panel"], [class*="Panel"], [class*="detail"], [class*="slide"]').first();
  if (await panel.isVisible()) {
    await panel.evaluate(el => el.scrollTop = el.scrollHeight);
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'tests/e2e/screenshots/scroll-02-bottom.png', fullPage: true });
  }

  // Also try scrolling the main content area
  await page.evaluate(() => {
    const panels = document.querySelectorAll('div');
    for (const p of panels) {
      if (p.scrollHeight > p.clientHeight + 100) {
        p.scrollTop = p.scrollHeight;
      }
    }
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'tests/e2e/screenshots/scroll-03-scrolled.png', fullPage: true });

  // Check for video anywhere in DOM
  const videos = await page.locator('video').all();
  console.log('Video elements in DOM:', videos.length);

  // Check for video source elements
  const sources = await page.locator('video source, video[src]').all();
  console.log('Video sources:', sources.length);

  // Check all img tags for R2
  const r2Images = await page.locator('img[src*="r2.dev"]').all();
  console.log('R2 images:', r2Images.length);

  // Dump the panel HTML to see what's there
  const panelHTML = await page.evaluate(() => {
    // Find the detail panel content
    const body = document.body.innerHTML;
    const r2Match = body.match(/r2\.dev[^"'<>]{0,100}/g);
    return { r2urls: r2Match, hasVideo: body.includes('<video') };
  });
  console.log('Panel data:', JSON.stringify(panelHTML));
});
