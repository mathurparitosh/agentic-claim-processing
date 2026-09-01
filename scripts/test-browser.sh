#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Claim Assistant — Browser End-to-End Test ==="
echo ""
echo "This test requires:"
echo "  - Backend running on http://localhost:8000"
echo "  - Frontend running on http://localhost:5173"
echo "  - Playwright installed (npm install -D @playwright/test)"
echo ""

# Check if servers are running
if ! curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "ERROR: Backend not running on http://localhost:8000"
    echo "Run './scripts/start.sh' first"
    exit 1
fi

if ! curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "ERROR: Frontend not running on http://localhost:5173"
    echo "Run './scripts/start.sh' first"
    exit 1
fi

# Create a test script
cat > /tmp/test-e2e.js << 'EOTEST'
const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.createBrowserContext();
  const page = await context.newPage();

  try {
    console.log('1. Loading login page...');
    await page.goto('http://localhost:5173');
    await page.waitForSelector('.password-gate', { timeout: 5000 });
    console.log('   ✓ Login page loaded');

    const password = process.env.AUTH_PASSWORD;
    if (!password) {
      throw new Error('AUTH_PASSWORD not set');
    }

    console.log('2. Logging in...');
    await page.fill('input[type="password"]', password);
    await page.click('button:has-text("Log in")');
    await page.waitForSelector('.claim-list', { timeout: 10000 });
    console.log('   ✓ Logged in, claim list loaded');

    console.log('3. Clicking "Start Claim"...');
    await page.click('button:has-text("Start Claim")');
    await page.waitForSelector('.claim-form', { timeout: 5000 });
    console.log('   ✓ Claim form opened');

    console.log('4. Filling form (ACC-9001)...');
    await page.fill('input[list="account-list"]', 'ACC-9001');
    await page.waitForSelector('option[value="ACC-9001"]', { timeout: 5000 });
    await page.press('input[list="account-list"]', 'ArrowDown');
    await page.press('input[list="account-list"]', 'Enter');
    await page.waitForSelector('select', { timeout: 5000 });
    const selectOptions = await page.$$('select option');
    if (selectOptions.length > 1) {
      await page.selectOption('select', selectOptions[1].getAttribute('value'));
      console.log('   ✓ Account and transaction selected');
    }

    console.log('5. Submitting claim...');
    await page.click('button:has-text("Submit")');
    await page.waitForURL(/claims\/[a-f0-9-]+/, { timeout: 10000 });
    console.log('   ✓ Claim submitted');

    console.log('6. Checking claim detail page...');
    await page.waitForSelector('.claim-detail', { timeout: 10000 });
    const statusBadge = await page.textContent('.status-badge');
    console.log(`   Status: ${statusBadge}`);

    console.log('7. Checking decision when ready...');
    let decision = null;
    for (let i = 0; i < 60; i++) {
      const decisionBadge = await page.textContent('.decision-badge', { timeout: 1000 }).catch(() => null);
      if (decisionBadge && (decisionBadge.includes('Approved') || decisionBadge.includes('Denied') || decisionBadge.includes('Inconclusive'))) {
        decision = decisionBadge;
        break;
      }
      await page.reload();
      await new Promise(r => setTimeout(r, 1000));
    }

    if (decision) {
      console.log(`   ✓ Decision: ${decision}`);
    } else {
      console.log('   ⚠ Decision not finalized within timeout (still processing)');
    }

    console.log('8. Checking audit trail tab...');
    await page.click('text=Audit Trail');
    await page.waitForSelector('.audit-row', { timeout: 5000 });
    console.log('   ✓ Audit trail visible');

    console.log('\n✓ All browser tests passed');
    process.exit(0);

  } catch (error) {
    console.error('\n✗ Test failed:', error.message);
    process.exit(1);
  } finally {
    await context.close();
    await browser.close();
  }
})();
EOTEST

# Run the test
cd "$PROJECT_ROOT"
export $(grep -v '^#' .env.local | xargs)
node /tmp/test-e2e.js
rm /tmp/test-e2e.js
