import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import Redis from 'ioredis';
import { signIn } from './support';

// The window is cached in Redis for twenty seconds, and /__reset only resets the
// mock: without this one test's scan would be what the next one reads.
const redis = new Redis(process.env.REDIS_URL ?? 'redis://localhost:6379/15');

const scans = async (request: APIRequestContext) =>
	(await (await request.get('http://localhost:8787/__sync-scans')).json()).scans as number;

const rows = (page: Page) => page.locator('[data-accordion-toggle]');

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	const cached = await redis.keys('ow:syncs:*');
	if (cached.length) await redis.del(...cached);
	await signIn(page);
});

test.afterAll(async () => {
	await redis.quit();
});

test('adds the window up, then pages through it', async ({ page }) => {
	await page.goto('/syncs');

	// Skipped syncs found nothing new: done, so the figures cover every run.
	await expect(page.getByText('45 syncs from 3 users')).toBeVisible();
	await expect(rows(page)).toHaveCount(20);

	await page.getByRole('link', { name: 'Next page' }).first().click();
	await expect(page).toHaveURL(/page=2/);
	await expect(page.getByText(/21–40\s*of 45/)).toBeVisible();

	await page.getByRole('link', { name: 'Page 3' }).click();
	await expect(rows(page)).toHaveCount(5);
});

test('a filter goes to the backend and starts again from page one', async ({ page }) => {
	await page.goto('/syncs?page=2');

	await page.getByLabel('Status', { exact: true }).selectOption('failed');
	await expect(page).not.toHaveURL(/page=/);
	await expect(page).toHaveURL(/status=failed/);
	await expect(rows(page)).toHaveCount(4);
	await expect(page.getByText('4 syncs from')).toBeVisible();

	await page.getByLabel('Status', { exact: true }).selectOption('cancelled');
	await expect(page.getByText('No syncs match these filters')).toBeVisible();
});

test('scans every buffer once per window, and again only on Refresh', async ({ page, request }) => {
	await page.goto('/syncs');
	await expect(rows(page)).toHaveCount(20);
	expect(await scans(request)).toBe(1);

	// Paging reads the cached window, as the old dashboard's every page change did not.
	await page.getByRole('link', { name: 'Page 2' }).click();
	await expect(page).toHaveURL(/page=2/);
	expect(await scans(request)).toBe(1);

	await page.getByRole('button', { name: 'Refresh' }).click();
	await expect.poll(() => scans(request)).toBe(2);
	// Still on page two: the refresh keeps the reader's place.
	await expect(page).toHaveURL(/page=2/);
});

test('an open run shows what Postgres kept, or says a live one is not kept', async ({ page }) => {
	await page.goto('/syncs?source=backfill');

	await rows(page).first().click();
	const stored = page.getByText('Stored record').locator('..');
	await expect(stored.getByText('Historical')).toBeVisible();
	await expect(stored.getByText('23 Jun – 23 Sept 2026').first()).toBeVisible();
	// Per data type, since "partial" alone cannot say which of them failed.
	await expect(stored.getByText('Workouts')).toBeVisible();
	await expect(stored.getByText('rate_limited: Provider rate limit reached')).toBeVisible();
	await expect(stored.getByText('attempt 2')).toBeVisible();

	await page.goto('/syncs?source=webhook');
	await rows(page).first().click();
	await expect(
		page.getByText(/None — a live sync is only kept in the 24-hour buffer/)
	).toBeVisible();
});

test('the user on a run links to their page', async ({ page }) => {
	await page.goto('/syncs');

	await page.getByRole('link', { name: '00000000', exact: true }).first().click();
	await expect(page).toHaveURL(/\/users\/00000000-0000-4000-8000-00000000000[789]$/);
});
