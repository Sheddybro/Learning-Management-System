/* Screenshots of local fictional accounts at desktop and mobile viewport sizes. */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const root = 'http://127.0.0.1:8765';
const output = path.resolve(__dirname, '../docs/audit/screenshots');
const password = 'OnlyForLocalScreenshotAudit2026!';
const cases = {
  guest: ['/users/', '/users/login/', '/users/application-portal/'],
  superadmin: ['/users/dashboard/', '/core/institutions/', '/academics/students/'],
  school_admin: ['/users/dashboard/', '/academics/students/', '/attendance/'],
  teacher: ['/users/teacher/dashboard/', '/academics/classes/', '/assessment/dashboard/'],
  student: ['/users/dashboard/', '/academics/subjects/', '/assessment/dashboard/'],
  parent: ['/users/parent/dashboard/', '/communication/notifications/', '/finance/dashboard/'],
  accountant: ['/users/dashboard/', '/finance/dashboard/', '/finance/invoices/'],
  librarian: ['/users/dashboard/', '/library/', '/library/books/'],
};

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const results = [];
  for (const [role, urls] of Object.entries(cases)) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    if (role !== 'guest') {
      await page.goto(root + '/users/login/', { waitUntil: 'domcontentloaded' });
      await page.locator('input[name="email"]').fill(`ui-${role}@example.test`);
      await page.locator('input[name="password"]').fill(password);
      await page.locator('#loginButton').click();
      await page.waitForLoadState('domcontentloaded');
    }
    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      for (const [size, dimensions] of Object.entries({ desktop: [1440, 900], mobile: [390, 844] })) {
        await page.setViewportSize({ width: dimensions[0], height: dimensions[1] });
        let status = 'network-error';
        try {
          const response = await page.goto(root + url, { waitUntil: 'domcontentloaded', timeout: 25000 });
          status = response?.status() ?? 'unknown';
        } catch (error) {
          status = `ERROR ${String(error.message).slice(0, 90)}`;
        }
        const filename = `${role}-${i + 1}-${size}.png`;
        await page.screenshot({ path: path.join(output, filename), fullPage: false });
        const title = await page.title();
        results.push({ role, page: url, viewport: size, status, title, screenshot: filename, final_url: page.url() });
        console.log('CAPTURE', role, url, size, status);
      }
    }
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(path.resolve(__dirname, '../docs/audit/screenshot_results.json'), JSON.stringify(results, null, 2));
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
