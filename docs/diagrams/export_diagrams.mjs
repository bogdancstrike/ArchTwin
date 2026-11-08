// Export each diagram HTML to a standalone .svg and a 2x .png (diagram-design export procedure).
// Usage: node export_diagrams.mjs   (requires the `playwright` npm package + Chromium)
import { chromium } from 'playwright';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const dir = process.argv[2] ?? dirname(fileURLToPath(import.meta.url));
const FONTS = "@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&amp;family=Geist:wght@400;500;600&amp;family=Geist+Mono:wght@400;500;600&amp;display=swap');";
const files = readdirSync(dir).filter((f) => f.endsWith('.html'));

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1280, height: 900 } });
for (const f of files) {
  const html = readFileSync(join(dir, f), 'utf8');
  let svg = html.match(/<svg[\s\S]*?<\/svg>/)[0];
  svg = svg.replace('<defs>', `<defs><style>${FONTS}</style>`);
  svg = svg.replace(/(fill|stroke)="rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d*\.?\d+)\s*\)"/g,
    (_, a, r, g, b, o) => `${a}="#${[r, g, b].map((v) => (+v).toString(16).padStart(2, '0')).join('')}" ${a}-opacity="${o}"`);
  svg = svg.replace(/(fill|stroke)="transparent"/g, '$1="none"');
  writeFileSync(join(dir, f.replace('.html', '.svg')), `<?xml version="1.0" encoding="UTF-8"?>\n${svg}\n`);
  await page.goto(pathToFileURL(join(dir, f)).href);
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.locator('svg').first().screenshot({ path: join(dir, f.replace('.html', '.png')) });
  console.log('exported', f);
}
await browser.close();
