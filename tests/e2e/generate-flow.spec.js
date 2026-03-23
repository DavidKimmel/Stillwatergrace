const { test, expect } = require('@playwright/test');

test.describe('Generate Single Day Flow', () => {
  test.setTimeout(180000); // 3 min for full pipeline

  test('click Generate and verify full pipeline runs', async ({ page }) => {
    // Listen for API requests
    const apiRequests = [];
    const apiResponses = [];

    page.on('request', req => {
      if (req.url().includes('/api/')) {
        apiRequests.push({ method: req.method(), url: req.url() });
      }
    });

    page.on('response', async res => {
      if (res.url().includes('/api/')) {
        let body = null;
        try { body = await res.json(); } catch {}
        apiResponses.push({
          url: res.url(),
          status: res.status(),
          body: body,
        });
      }
    });

    // Load dashboard
    await page.goto('http://localhost:5175');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'tests/e2e/screenshots/gen-01-initial.png' });

    // Find the Generate button
    const generateBtn = page.getByRole('button', { name: /generate/i });
    await expect(generateBtn).toBeVisible();
    console.log('Generate button found');

    // Click it
    await generateBtn.click();
    console.log('Clicked Generate');

    // Wait for API call to complete (may take a while if generating content + reel)
    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'tests/e2e/screenshots/gen-02-after-click.png' });

    // Log all API calls made
    console.log('\n=== API Requests ===');
    for (const req of apiRequests) {
      console.log(`${req.method} ${req.url}`);
    }

    console.log('\n=== API Responses ===');
    for (const res of apiResponses) {
      console.log(`${res.status} ${res.url}`);
      if (res.body) {
        console.log('  Body:', JSON.stringify(res.body).substring(0, 300));
      }
    }

    // Check if any content cards appeared or updated
    await page.waitForTimeout(2000);
    const cards = await page.locator('[class*="card"], [class*="Card"]').all();
    console.log('\nContent cards found:', cards.length);

    // Check for video/image elements
    const videos = await page.locator('video').all();
    const images = await page.locator('img[src*="r2"]').all();
    console.log('Video elements:', videos.length);
    console.log('R2 image elements:', images.length);

    // Check for "No img" text (means no image was generated)
    const noImgElements = await page.getByText('No img').all();
    console.log('"No img" elements:', noImgElements.length);

    // Final screenshot
    await page.screenshot({ path: 'tests/e2e/screenshots/gen-03-final-state.png', fullPage: true });
  });
});
