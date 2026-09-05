/* Run with FORGE_URL=http://127.0.0.1:8877 node tests/ui_smoke.js */
const { chromium } = require('playwright');
const base = process.env.FORGE_URL || 'http://127.0.0.1:8877';
const viewports = [{ width: 1920, height: 1080 }, { width: 1366, height: 768 }, { width: 820, height: 1000 }, { width: 390, height: 844 }];
(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base, { waitUntil: 'networkidle' });
    await page.waitForSelector('.mission');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (overflow) throw new Error(`Horizontal overflow at ${viewport.width}px`);
    for (const view of ['map', 'review', 'today']) {
      await page.click(`[data-view="${view}"]`);
      await page.waitForTimeout(100);
    }
    const start = page.locator('.mission [data-timer="start"]:not([disabled])').first();
    await start.click();
    await page.waitForSelector('.mission [data-timer="pause"]');
    await page.locator('.mission [data-timer="pause"]').first().click();
    await page.locator('.mission [data-finish]').first().click();
    await page.waitForSelector('#finish-dialog[open]');
    await page.click('#finish-dialog [data-close]');
    await page.locator('header details > summary').click();
    await page.click('#edit');
    await page.waitForSelector('#edit-dialog[open] .editor-row');
    await page.click('#edit-dialog [data-close]');
    if (errors.length) throw new Error(errors.join('; '));
    await page.close();
  }
  await browser.close();
  console.log('FORGE Playwright smoke test passed at four viewport sizes.');
})().catch(error => { console.error(error); process.exit(1); });
