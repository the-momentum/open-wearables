import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const DATA = `/users/${USER}/data`;
const QUARTER = `${DATA}?from=2026-06-13&to=2026-09-10`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('plots each data type over time, not a table of totals', async ({ page }) => {
	await page.goto(QUARTER);

	const types = page.getByRole('region').filter({ hasText: 'Series types' });
	await expect(types.getByText('Heart rate')).toBeVisible();
	// The acronym survives the slug, rather than reading "Vo2 max".
	await expect(types.getByText('VO2 max')).toBeVisible();

	// One cell per day across the window, carrying its own date and count.
	const cells = types.locator('span[title*="2026-"]');
	expect(await cells.count()).toBeGreaterThan(400);
	await expect(cells.first()).toHaveAttribute('title', /2026-06-13 · \d+/);
});

test('gives providers and data types a section each, without repeating either', async ({
	page
}) => {
	await page.goto(QUARTER);

	// Providers over time sit with the share bar they explain: the legend names
	// them, and the heatmap row beside it carries the same name as its label.
	const collected = page.getByRole('region').filter({ hasText: 'Data collected' });
	await expect(collected.getByTitle('Garmin', { exact: true })).toBeVisible();
	await expect(collected.getByText('Heart rate')).toHaveCount(0);

	const types = page.getByRole('region').filter({ hasText: 'Series types' });
	await expect(types.getByText('Garmin')).toHaveCount(0);
});

test('narrowing a provider costs no round trip', async ({ page }) => {
	await page.goto(QUARTER);

	// A re-run load fetches __data.json, and that is what used to scroll the
	// page back to its header. Narrowing shrinks the panels, so the scroll
	// position itself cannot be asserted — the absence of the load can.
	const reloads: string[] = [];
	page.on('request', (request) => {
		if (request.url().includes('__data.json')) reloads.push(request.url());
	});

	await page.getByRole('button', { name: 'Oura', exact: true }).click();

	await expect(page).toHaveURL(`${QUARTER}&provider=oura`);
	await expect(page.getByText('7420')).toBeVisible();
	expect(reloads).toEqual([]);
});

test('narrows every panel it can, and labels the ones it cannot', async ({ page }) => {
	await page.goto(QUARTER);
	await page.getByRole('button', { name: 'Oura', exact: true }).click();

	await expect(page.getByRole('button', { name: 'Oura', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);

	// Totals and the provider timeline follow the filter.
	const collected = page.getByRole('region').filter({ hasText: 'Data collected' });
	await expect(collected.getByText('7420')).toBeVisible();
	await expect(collected.getByTitle('Oura', { exact: true })).toBeVisible();
	await expect(collected.getByTitle('Garmin', { exact: true })).toHaveCount(0);

	// Series types drop to totals rather than plotting every provider under a
	// heading that names one.
	const types = page.getByRole('region').filter({ hasText: 'Series types' });
	await expect(types.getByText('What Oura delivers')).toBeVisible();
	await expect(types.locator('span[title*="2026-"]')).toHaveCount(0);
	await expect(types.getByText('Oxygen saturation')).toBeVisible();
	await expect(types.getByText('Steps')).toHaveCount(0);

	// And the one that cannot be narrowed at all says so.
	const workouts = page.getByRole('region').filter({ hasText: 'Workout types' });
	await expect(workouts.getByText('Across every provider')).toBeVisible();
});

test('keeps the chosen provider when the period changes', async ({ page }) => {
	await page.goto(QUARTER);
	await page.getByRole('button', { name: 'Oura', exact: true }).click();

	// The provider lives in page.state, which page.url does not carry, so a
	// period link has to put it back or the filter clears itself.
	await page.getByRole('link', { name: 'All time' }).click();

	await expect(page).toHaveURL(`${DATA}?provider=oura`);
	await expect(page.getByRole('button', { name: 'Oura', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(page.getByText('From Oura')).toBeVisible();
});

test('offers all time, a single day, and a range', async ({ page }) => {
	await page.goto(QUARTER);
	await expect(page.getByRole('textbox', { name: 'From' })).toHaveValue('2026-06-13');

	await page.getByRole('link', { name: 'Day' }).click();
	await expect(page.getByRole('textbox', { name: 'Day' })).toBeVisible();

	await page.getByRole('link', { name: 'All time' }).click();
	await expect(page).toHaveURL(DATA);
});

test('keeps the provider filter visible while stepping through days', async ({ page }) => {
	await page.goto(QUARTER);
	const filter = page.getByRole('group', { name: 'Provider' });
	await expect(filter).toBeVisible();

	// It lists connections, not whatever the period happens to hold, so it does
	// not vanish and reappear as the day changes.
	await page.getByRole('link', { name: 'Day' }).click();
	await expect(filter).toBeVisible();
	await page.getByRole('textbox', { name: 'Day' }).fill('2026-01-15');
	await expect(filter).toBeVisible();
});

test('falls back to bars for a single day, where a timeline is one column', async ({ page }) => {
	await page.goto(`${DATA}?from=2026-09-10&to=2026-09-10`);

	const types = page.getByRole('region').filter({ hasText: 'Series types' });
	await expect(types.getByText('Measurements recorded that day')).toBeVisible();
	await expect(types.getByText('Heart rate')).toBeVisible();
	// No colour ramp to read on one bucket.
	await expect(types.getByText('Less')).toHaveCount(0);

	await types.getByRole('button', { name: 'Show all 9' }).click();
	await expect(types.getByText('UV exposure')).toBeVisible();
});
