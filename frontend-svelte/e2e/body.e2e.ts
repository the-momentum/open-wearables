import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const UNCONNECTED = '00000000-0000-4000-8000-000000000003';
const BODY = `/users/${USER}/body`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('shows the body as it stands, dashing what was never measured', async ({ page }) => {
	await page.goto(BODY);

	const figures = page.locator('[aria-label="Body composition"]');
	await expect(figures.getByText('74.3 kg')).toBeVisible();
	await expect(figures.getByText('22.7')).toBeVisible();

	// This user has no body-fat reading, and a fixed shape says so rather than
	// quietly dropping the slot.
	await expect(figures.getByText('Body fat')).toBeVisible();
	await expect(figures.getByText('—')).toBeVisible();

	// The endpoint takes no provider, so the one it read from is named instead.
	await expect(page.getByText('Latest reading from Garmin')).toBeVisible();
});

test('plots a vital over the period, averaged to a point a day', async ({ page }) => {
	await page.goto(BODY);

	// HRV arrives dozens of times a day; left alone it would overrun a page and be
	// cut. Ninety days of it is ninety points.
	const hrv = page.getByText('HRV (RMSSD)', { exact: true }).locator('..').locator('..');
	await expect(hrv.getByText('90 days')).toBeVisible();
	await expect(hrv.getByText(/^low /)).toBeVisible();

	// Blood oxygen reads as a symbol, not as the backend's word for it.
	await expect(page.getByText('%', { exact: true })).toBeVisible();
});

test('draws no line for a vital measured once', async ({ page }) => {
	await page.goto(BODY);

	// Scoped to the trends: "Weight" also labels a figure above them, and a bare
	// text match would find that one.
	const trends = page.getByText('Vitals over the period').locator('..');
	await expect(trends.getByText('Resting heart rate')).toBeVisible();

	// Weight has a single reading. One point is no trend, and a lone dot says less
	// than the figure already above it.
	await expect(trends.getByText('Weight')).toHaveCount(0);
});

test('narrows the trend window without touching the figures above', async ({ page }) => {
	await page.goto(`${BODY}?from=2026-09-01&to=2026-09-21`);

	// Three weeks, not the ninety-day default, so the trends shrink with it.
	await expect(page.getByText('90 days')).toHaveCount(0);
	await expect(page.getByText(/^\d\d days$/).first()).toBeVisible();

	// The snapshot is the latest reading whatever window is chosen.
	await expect(page.getByText('74.3 kg')).toBeVisible();
});

test('says so when the user has no body data at all', async ({ page }) => {
	await page.goto(`/users/${UNCONNECTED}/body`);

	await expect(page.getByText('No body data recorded')).toBeVisible();
	await expect(page.locator('[aria-label="Body composition"]')).toHaveCount(0);
});
