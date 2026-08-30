import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../screenshots");
const baseUrl = "http://127.0.0.1:5173";

async function clearSession(page) {
  await page.goto(baseUrl);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.reload({ waitUntil: "networkidle" });
}

async function clickFirstMatchingButton(page, pattern) {
  const button = page.getByRole("button", { name: pattern }).first();
  await button.waitFor({ state: "visible", timeout: 15000 });
  await button.click();
}

async function clickEnabledButton(page, patterns) {
  for (const pattern of patterns) {
    const button = page.getByRole("button", { name: pattern }).first();
    if (await button.isVisible().catch(() => false)) {
      if (await button.isEnabled().catch(() => false)) {
        await button.click();
        return;
      }
    }
  }
  throw new Error(`No enabled button matched: ${patterns.map(String).join(", ")}`);
}

async function waitForChapter(page, label) {
  await page.locator(`nav[aria-label="Recovery sequence"] >> text=${label}`).first().waitFor({
    state: "visible",
    timeout: 15000,
  });
  await page.waitForTimeout(400);
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await clearSession(page);
  await page.screenshot({ path: path.join(outDir, "checkpoint-1-empty.png"), fullPage: true });

  await clickFirstMatchingButton(page, /^start recovery demo$/i);
  await page.waitForSelector("text=SYN-EVT", { timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, "checkpoint-2-incident-created.png"), fullPage: true });

  await clickFirstMatchingButton(page, /publish yard forecast/i);
  await page.waitForTimeout(600);
  await clickFirstMatchingButton(page, /start recovery agent/i);
  await page.waitForTimeout(600);
  await clickFirstMatchingButton(page, /advance agent once/i);
  await page.waitForTimeout(600);
  await clickFirstMatchingButton(page, /publish discharge evidence/i);
  await page.waitForTimeout(600);
  await clickEnabledButton(page, [/advance agent once/i, /advance orchestration/i]);
  await waitForChapter(page, "Adapt");
  await page.waitForSelector("text=Chapter 4 · Adapt", { timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, "checkpoint-3-adapt.png"), fullPage: true });

  await clickEnabledButton(page, [/advance orchestration/i, /advance agent once/i]);
  await waitForChapter(page, "Coordinate");
  await page.waitForSelector("text=Chapter 5 · Coordinate", { timeout: 15000 });
  await page.getByRole("button", { name: /approve request/i }).first().waitFor({
    state: "visible",
    timeout: 15000,
  });
  await page.screenshot({ path: path.join(outDir, "checkpoint-4-coordinate.png"), fullPage: true });

  await browser.close();
  console.log("Saved checkpoint screenshots to", outDir);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
