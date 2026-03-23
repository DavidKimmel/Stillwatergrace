const { test, expect } = require('@playwright/test');

test('click content card and check for preview', async ({ page }) => {
  test.setTimeout(30000);

  await page.goto('http://localhost:5175');
  await page.waitForLoadState('networkidle');

  // Navigate to the week with content (Mar 22 is Sunday)
  // The calendar shows Mar 16-22, content is on Sunday 3/22
  await page.screenshot({ path: 'tests/e2e/screenshots/click-01-calendar.png' });

  // Find the content card (has "daily_devotion" or "Psa" text)
  const card = page.locator('text=daily_devotion').first();
  if (await card.isVisible()) {
    await card.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'tests/e2e/screenshots/click-02-after-click.png', fullPage: true });

    // Check for video player, detail panel, or modal
    const videos = await page.locator('video').all();
    const iframes = await page.locator('iframe').all();
    const modals = await page.locator('[class*="modal"], [class*="Modal"], [class*="panel"], [class*="Panel"], [class*="detail"], [class*="Detail"], [class*="drawer"], [class*="Drawer"]').all();

    console.log('Video elements:', videos.length);
    console.log('Iframes:', iframes.length);
    console.log('Modals/panels:', modals.length);

    // Check for any R2 URLs in the page
    const html = await page.content();
    const r2urls = html.match(/r2\.dev[^"']*/g);
    if (r2urls) {
      console.log('R2 URLs found:');
      r2urls.forEach(u => console.log('  ', u));
    } else {
      console.log('No R2 URLs found in page');
    }

    // Log visible text in any new panels
    const bodyText = await page.textContent('body');
    if (bodyText.includes('Approve') || bodyText.includes('Reject') || bodyText.includes('Preview')) {
      console.log('Found action buttons (Approve/Reject/Preview)');
    }
  } else {
    console.log('No content card visible');
  }
});
