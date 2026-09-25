import { expect, test, type APIRequestContext } from '@playwright/test';
import Redis from 'ioredis';
import { signIn } from './support';

// The page caches the estimate in Redis, and /__reset only resets the mock:
// without this a save in one test would be what the next one reads.
const redis = new Redis(process.env.REDIS_URL ?? 'redis://localhost:6379/15');

const scans = async (request: APIRequestContext) =>
	(await (await request.get('http://localhost:8787/__lifecycle-scans')).json()).scans as number;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await redis.del('ow:lifecycle');
	await signIn(page);
});

test.afterAll(async () => {
	await redis.quit();
});

test('shows where the storage goes, in the units the API uses', async ({ page }) => {
	await page.goto('/settings/data-lifecycle');

	const storage = page.getByRole('region', { name: 'Storage' });
	await expect(storage.getByText('458.0 MB', { exact: true })).toBeVisible();
	await expect(storage.getByText('475.0 MB', { exact: true })).toBeVisible();
	// 56 KB of a 475 MB database is small, not absent.
	await expect(storage.getByText(/Archive\s*56\.0 KB · <1%/)).toBeVisible();
	// A planner statistic, and the page says so rather than printing it as a count.
	await expect(storage.getByText(/~1\.9K rows/)).toBeVisible();
});

test('draws the draft, not what is saved, so a change can be seen before it is made', async ({
	page
}) => {
	await page.goto('/settings/data-lifecycle');

	const projection = page.getByRole('region', { name: 'Growth projection' });
	await expect(projection.getByText('O(n) · linear')).toBeVisible();

	await page.getByRole('switch', { name: 'Delete old data' }).click();
	// Nothing saved yet — the class and the curve already follow the switch.
	await expect(projection.getByText('O(1) · bounded')).toBeVisible();
	await expect(page.getByText('Lifecycle policy changed')).toBeVisible();
});

test('saves a policy and reads it back', async ({ page }) => {
	await page.goto('/settings/data-lifecycle');

	await page.getByRole('switch', { name: 'Archive old samples' }).click();
	await page.getByLabel('Archive data older than').fill('30');
	await page.getByRole('button', { name: 'Save changes' }).click();

	await expect(page.getByText('Lifecycle policy changed')).toHaveCount(0);
	await page.reload();
	await expect(page.getByLabel('Archive data older than')).toHaveValue('30');
	await expect(page.getByText('O(n) · efficient')).toBeVisible();
});

test('refuses a number the API would reject, and says why', async ({ page }) => {
	await page.goto('/settings/data-lifecycle');

	await page.getByRole('switch', { name: 'Archive old samples' }).click();
	await page.getByLabel('Archive data older than').fill('0');

	await expect(page.getByText(/1 to 3650/)).toBeVisible();
	await expect(page.getByRole('button', { name: 'Save changes' })).toBeDisabled();
});

test('warns when deletion comes before archival', async ({ page }) => {
	await page.goto('/settings/data-lifecycle');

	await page.getByRole('switch', { name: 'Archive old samples' }).click();
	await page.getByLabel('Archive data older than').fill('90');
	await page.getByRole('switch', { name: 'Delete old data' }).click();
	await page.getByLabel('Delete data older than').fill('30');

	await expect(page.getByText(/archival never happens/)).toBeVisible();
});

test('will not run a policy that has not been saved', async ({ page }) => {
	await page.goto('/settings/data-lifecycle');

	const run = page.getByRole('button', { name: 'Run now' });
	await expect(run).toBeDisabled();
	await expect(page.getByText('Nothing to run')).toBeVisible();

	// The old dashboard saved on the way and then ran — with deletion on, that
	// deleted by a rule nobody had confirmed.
	await page.getByRole('switch', { name: 'Delete old data' }).click();
	await expect(run).toBeDisabled();
	await expect(page.getByText(/Save your changes first/)).toBeVisible();
});

test('runs the saved policy after confirming, and warns when it deletes', async ({ page }) => {
	await page.goto('/settings/data-lifecycle');

	await page.getByRole('switch', { name: 'Delete old data' }).click();
	await page.getByRole('button', { name: 'Save changes' }).click();
	await expect(page.getByText('Lifecycle policy changed')).toHaveCount(0);

	await page.getByRole('button', { name: 'Run now' }).click();
	const dialog = page.getByRole('dialog');
	await expect(dialog).toContainText('deleted permanently');
	await dialog.getByRole('button', { name: 'Run now' }).click();

	await expect(page.getByText(/Queued\. It runs in the background/)).toBeVisible();
});

test('scans the series table once however often the tab is opened', async ({ page, request }) => {
	await page.goto('/settings/data-lifecycle');
	await expect(page.getByRole('region', { name: 'Storage' })).toBeVisible();

	await page.getByRole('link', { name: 'Team' }).click();
	await page.getByRole('link', { name: /Data Lifecycle/ }).click();
	await expect(page.getByRole('region', { name: 'Storage' })).toBeVisible();

	// Each call is a pass over the largest table on a customer's database.
	expect(await scans(request)).toBe(1);
});

test('does not scan again to show what a save just returned', async ({ page, request }) => {
	await page.goto('/settings/data-lifecycle');

	await page.getByRole('switch', { name: 'Archive old samples' }).click();
	await page.getByRole('button', { name: 'Save changes' }).click();
	await expect(page.getByText('Lifecycle policy changed')).toHaveCount(0);

	// The GET that opened the page and the PUT that saved — the PUT answers with
	// fresh sizes, so the reload after it is served from that.
	expect(await scans(request)).toBe(2);
});

test('opens without waiting for the estimate', async ({ page }) => {
	// A miss streams: the skeleton is up and the tabs work while the backend
	// is still scanning.
	await page.goto('/settings/data-lifecycle');
	await expect(page.getByRole('navigation', { name: 'Settings sections' })).toBeVisible();
	await expect(page.getByRole('region', { name: 'Storage' })).toBeVisible();
});

test('fits a phone', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/settings/data-lifecycle');
	await expect(page.getByRole('region', { name: 'Storage' })).toBeVisible();

	const width = await page.evaluate(() => document.documentElement.scrollWidth);
	expect(width).toBeLessThanOrEqual(390);
});
