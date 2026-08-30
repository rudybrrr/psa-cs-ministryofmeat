import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../screenshots/final");
const baseUrl = process.env.PSA_SCREENSHOT_BASE_URL ?? "http://127.0.0.1:5173";

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
        await page.waitForLoadState("networkidle").catch(() => undefined);
        await page.waitForTimeout(500);
        return;
      }
    }
  }
  throw new Error(`No enabled button matched: ${patterns.map(String).join(", ")}`);
}

async function advanceUntilActionVisible(page, actionPattern, maxAttempts = 4) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const actionButton = page.getByRole("button", { name: actionPattern }).first();
    if (await actionButton.isVisible().catch(() => false)) {
      if (await actionButton.isEnabled().catch(() => false)) {
        return;
      }
    }

    const advancePatterns = [/advance orchestration/i, /advance agent once/i];
    let advanced = false;
    for (const pattern of advancePatterns) {
      const advance = page.getByRole("button", { name: pattern }).first();
      if (await advance.isVisible().catch(() => false)) {
        if (await advance.isEnabled().catch(() => false)) {
          await advance.click();
          await page.waitForLoadState("networkidle").catch(() => undefined);
          await page.waitForTimeout(600);
          advanced = true;
          break;
        }
      }
    }

    if (!advanced) {
      break;
    }
  }

  const actionButton = page.getByRole("button", { name: actionPattern }).first();
  await actionButton.waitFor({ state: "visible", timeout: 20000 });
  await expectEnabled(actionButton);
}

async function expectEnabled(locator) {
  await locator.waitFor({ state: "visible", timeout: 20000 });
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (await locator.isEnabled().catch(() => false)) {
      return;
    }
    await locator.page().waitForTimeout(200);
  }
  throw new Error("Button remained disabled");
}

async function waitForChapter(page, label) {
  await page.locator(`nav[aria-label="Recovery sequence"] >> text=${label}`).first().waitFor({
    state: "visible",
    timeout: 15000,
  });
  await page.waitForTimeout(400);
}

async function clickWorkspace(page, label) {
  await page.getByRole("button", { name: label }).click();
  await page.waitForTimeout(300);
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(outDir, name), fullPage: true });
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await clearSession(page);
  await screenshot(page, "01-guided-fresh.png");

  await clickFirstMatchingButton(page, /^start recovery demo$/i);
  await page.waitForSelector("text=SYN-EVT", { timeout: 15000 });
  await screenshot(page, "02-incident.png");

  await clickFirstMatchingButton(page, /publish yard forecast/i);
  await page.waitForTimeout(500);
  await screenshot(page, "03-optimize.png");

  await clickFirstMatchingButton(page, /start recovery agent/i);
  await page.waitForTimeout(500);
  await clickEnabledButton(page, [/advance orchestration/i, /advance agent once/i]);
  await page.waitForTimeout(500);
  await screenshot(page, "04-observe.png");

  await clickFirstMatchingButton(page, /publish discharge evidence/i);
  await page.waitForTimeout(500);
  await clickEnabledButton(page, [/advance agent once/i, /advance orchestration/i]);
  await waitForChapter(page, "Adapt");
  await screenshot(page, "05-adapt.png");

  await clickEnabledButton(page, [/advance orchestration/i, /advance agent once/i]);
  await waitForChapter(page, "Coordinate");
  await screenshot(page, "06-coordinate.png");

  await page.getByRole("button", { name: /approve request/i }).first().click();
  await page.waitForTimeout(400);
  await clickEnabledButton(page, [/advance orchestration/i, /advance agent once/i]);
  await page.waitForTimeout(400);
  await clickFirstMatchingButton(page, /simulate carrier response/i);
  await page.waitForTimeout(400);
  await clickEnabledButton(page, [/advance orchestration/i, /advance agent once/i]);
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: /approve counter/i }).first().click();
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(600);
  await page
    .getByRole("button", { name: /record syn-cnt-010 safety evidence/i })
    .first()
    .waitFor({ state: "visible", timeout: 20000 });
  await screenshot(page, "07-respond.png");

  await page.getByRole("button", { name: /record syn-cnt-010 safety evidence/i }).first().click();
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(600);
  await clickEnabledButton(page, [/advance orchestration/i, /advance agent once/i]);
  await waitForChapter(page, "Protect");
  await page.waitForSelector("text=ESCALATED", { timeout: 20000 }).catch(() => undefined);
  await page.waitForTimeout(500);
  await screenshot(page, "08-protect.png");

  await page.getByRole("button", { name: "Auto replay", exact: true }).click();
  await screenshot(page, "09-auto-replay.png");

  await page.getByRole("button", { name: "Guided demo", exact: true }).click();
  await clickWorkspace(page, "Recovery");
  await screenshot(page, "10-recovery-workspace.png");
  await clickWorkspace(page, "Containers");
  await screenshot(page, "11-containers-workspace.png");
  await clickWorkspace(page, "Carrier");
  await screenshot(page, "12-carrier-workspace.png");
  await clickWorkspace(page, "Evidence / Audit");
  await screenshot(page, "13-evidence-workspace.png");

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await screenshot(page, "14-resume-after-refresh.png");

  await browser.close();
  console.log("Saved final screenshots to", outDir);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
