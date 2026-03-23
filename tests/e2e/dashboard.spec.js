const { test, expect } = require('@playwright/test');

test.describe('Dashboard Generate Flow', () => {
  test.setTimeout(120000); // 2 min timeout for rendering

  test('should load dashboard and show calendar', async ({ page }) => {
    await page.goto('http://localhost:5175');
    await page.waitForLoadState('networkidle');

    // Take screenshot of initial state
    await page.screenshot({ path: 'tests/e2e/screenshots/01-dashboard-loaded.png', fullPage: true });

    // Check page loaded
    const title = await page.title();
    console.log('Page title:', title);

    // Log what we see
    const bodyText = await page.textContent('body');
    console.log('Body text (first 500 chars):', bodyText.substring(0, 500));
  });

  test('should find and click Generate button', async ({ page }) => {
    await page.goto('http://localhost:5175');
    await page.waitForLoadState('networkidle');

    // Look for any button with "Generate" text
    const generateButtons = await page.getByRole('button').filter({ hasText: /generate/i }).all();
    console.log('Found generate buttons:', generateButtons.length);

    if (generateButtons.length === 0) {
      // Try finding by text content anywhere
      const allButtons = await page.getByRole('button').all();
      for (const btn of allButtons) {
        const text = await btn.textContent();
        console.log('Button found:', text.trim());
      }

      // Also check for links or other clickable elements
      const links = await page.getByRole('link').all();
      for (const link of links) {
        const text = await link.textContent();
        if (text.trim()) console.log('Link found:', text.trim());
      }
    }

    await page.screenshot({ path: 'tests/e2e/screenshots/02-before-generate.png', fullPage: true });

    // Click the first generate button if found
    if (generateButtons.length > 0) {
      await generateButtons[0].click();
      console.log('Clicked Generate button');

      // Wait for response
      await page.waitForTimeout(5000);
      await page.screenshot({ path: 'tests/e2e/screenshots/03-after-generate.png', fullPage: true });

      // Check what appeared
      const updatedText = await page.textContent('body');
      console.log('After generate (first 500 chars):', updatedText.substring(0, 500));
    }
  });

  test('should show content with preview after generation', async ({ page }) => {
    await page.goto('http://localhost:5175');
    await page.waitForLoadState('networkidle');

    // Look for any content cards or posts
    const videos = await page.locator('video').all();
    console.log('Video elements found:', videos.length);

    const images = await page.locator('img').all();
    console.log('Image elements found:', images.length);

    // Check for any R2 URLs (content previews)
    const pageContent = await page.content();
    const r2Matches = pageContent.match(/r2\.dev/g);
    console.log('R2 URL references:', r2Matches ? r2Matches.length : 0);

    // Look for content status indicators
    const pendingBadges = await page.getByText(/pending/i).all();
    const approvedBadges = await page.getByText(/approved/i).all();
    console.log('Pending badges:', pendingBadges.length);
    console.log('Approved badges:', approvedBadges.length);

    await page.screenshot({ path: 'tests/e2e/screenshots/04-content-state.png', fullPage: true });
  });
});
