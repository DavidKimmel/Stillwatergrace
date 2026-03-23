const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 120000,
  use: {
    baseURL: 'http://localhost:5175',
    screenshot: 'on',
    trace: 'on-first-retry',
  },
});
