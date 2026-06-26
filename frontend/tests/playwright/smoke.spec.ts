import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
});

test('landing shell renders the analyst workspace', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'RetailIQ' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Map Explorer' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Candidate Sites' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Data Hub' })).toBeVisible();
  await expect(page.locator('.app-layout')).toHaveScreenshot('shell-home.png', {
    maxDiffPixelRatio: 0.02,
  });
});

test('candidate sites page opens the detail panel', async ({ page }) => {
  await page.goto('/sites');

  await expect(page.getByRole('heading', { name: 'Candidate Sites' })).toBeVisible();
  await page.getByText('87.5').click();
  await expect(page.getByText('AI Narrative Insight')).toBeVisible();
  await expect(page.getByText('Factor Breakdown')).toBeVisible();
  await expect(page.locator('.sites-container')).toHaveScreenshot('candidate-sites.png', {
    maxDiffPixelRatio: 0.02,
  });
});

test('map explorer shows the core controls', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Analysis Layers' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run Analysis' })).toBeVisible();
  await expect(page.locator('.map-explorer-container')).toHaveScreenshot('map-explorer-loading.png', {
    maxDiffPixelRatio: 0.02,
  });
});

test('data hub and analysis pages are reachable', async ({ page }) => {
  await page.goto('/data');
  await expect(page.getByRole('heading', { name: 'Data Hub' })).toBeVisible();
  await expect(page.locator('body')).toHaveScreenshot('data-hub.png', {
    maxDiffPixelRatio: 0.02,
  });

  await page.goto('/analysis');
  await expect(page.getByRole('heading', { name: 'Analysis Runs' })).toBeVisible();
  await expect(page.locator('body')).toHaveScreenshot('analysis-runs.png', {
    maxDiffPixelRatio: 0.02,
  });
});

test('mobile shell keeps the settings panel usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await expect(page.getByRole('link', { name: 'Map Explorer' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible();
  await page.getByRole('button', { name: 'Settings' }).click();
  await expect(page.getByRole('dialog', { name: 'Settings' })).toBeVisible();
  await expect(page.locator('.app-layout')).toHaveScreenshot('shell-mobile-settings.png', {
    maxDiffPixelRatio: 0.02,
  });
});
