const { test, expect } = require('@playwright/test');

test.describe('Generate 1 Day Full Pipeline', () => {
  test.setTimeout(180000);

  test('click Generate > 1 day and trace API calls', async ({ page }) => {
    const apiCalls = [];

    page.on('request', req => {
      if (req.url().includes('/api/')) {
        apiCalls.push({
          type: 'request',
          method: req.method(),
          url: req.url(),
          postData: req.postData(),
        });
        console.log(`>> ${req.method()} ${req.url()}`);
        if (req.postData()) console.log(`   Body: ${req.postData().substring(0, 200)}`);
      }
    });

    page.on('response', async res => {
      if (res.url().includes('/api/') && res.url().includes('generate')) {
        let body = null;
        try { body = await res.text(); } catch {}
        console.log(`<< ${res.status()} ${res.url()}`);
        if (body) console.log(`   Response: ${body.substring(0, 500)}`);
      }
    });

    // Load dashboard
    await page.goto('http://localhost:5175');
    await page.waitForLoadState('networkidle');

    // Click Generate to open dropdown
    const generateBtn = page.getByRole('button', { name: /generate/i });
    await generateBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'tests/e2e/screenshots/1day-01-dropdown.png' });

    // Click "1 day"
    const oneDayOption = page.getByText('1 day', { exact: true });
    await expect(oneDayOption).toBeVisible();
    await oneDayOption.click();
    console.log('Clicked "1 day"');

    // Wait for the API call and response
    await page.waitForTimeout(15000);
    await page.screenshot({ path: 'tests/e2e/screenshots/1day-02-after-generate.png' });

    // Log all API calls
    console.log('\n=== All API Calls ===');
    for (const call of apiCalls) {
      if (call.method === 'POST') {
        console.log(`POST ${call.url} body=${call.postData}`);
      }
    }

    // Check result on page
    const noImgCount = await page.getByText('No img').count();
    const videoCount = await page.locator('video').count();
    const imgWithR2 = await page.locator('img[src*="r2.dev"]').count();

    console.log('\n=== Dashboard State ===');
    console.log('No img labels:', noImgCount);
    console.log('Video elements:', videoCount);
    console.log('R2 images:', imgWithR2);

    // Check API logs for errors
    await page.screenshot({ path: 'tests/e2e/screenshots/1day-03-final.png', fullPage: true });
  });
});
