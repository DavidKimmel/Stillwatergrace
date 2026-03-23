const { test, expect } = require('@playwright/test');

test('click content card thumbnail and verify detail panel opens with video', async ({ page }) => {
  test.setTimeout(30000);

  await page.goto('http://localhost:5175');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'tests/e2e/screenshots/preview-01-initial.png' });

  // Find the card with the play button (Sunday 3/22 - has a rendered reel)
  // Click on the thumbnail area specifically
  const playIcon = page.locator('svg, [class*="play"], img[src*="r2"]').first();
  const cardWithReel = page.locator('text=Psa').first();

  if (await cardWithReel.isVisible()) {
    await cardWithReel.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'tests/e2e/screenshots/preview-02-after-click.png', fullPage: true });

    // Check for detail panel
    const videos = await page.locator('video').all();
    console.log('Video players found:', videos.length);

    // Check for approve/reject buttons
    const approveBtn = await page.getByRole('button', { name: /approve/i }).count();
    const rejectBtn = await page.getByRole('button', { name: /reject/i }).count();
    console.log('Approve buttons:', approveBtn);
    console.log('Reject buttons:', rejectBtn);

    // Check for any panel/drawer that opened
    const panels = await page.locator('[class*="slide"], [class*="drawer"], [class*="detail"], [class*="panel"], [class*="overlay"]').all();
    console.log('Panels/drawers:', panels.length);

    // Check what's visible now
    const pageText = await page.textContent('body');
    if (pageText.includes('Preview') || pageText.includes('preview')) console.log('Found "Preview" text');
    if (pageText.includes('Approve')) console.log('Found "Approve" text');
    if (pageText.includes('Caption')) console.log('Found "Caption" text');
    if (pageText.includes('Regenerate')) console.log('Found "Regenerate" text');

    // Look for the video source
    for (const vid of videos) {
      const src = await vid.getAttribute('src');
      console.log('Video src:', src);
    }
  } else {
    console.log('No content card with Psa found');
  }
});
