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

test('plots workout types over time, not just their totals', async ({ page }) => {
	await page.goto(QUARTER);

	const workouts = page.getByRole('region').filter({ hasText: 'Workout types' });
	await expect(workouts.getByText('Running')).toBeVisible();
	await expect(workouts.getByText('Strength training')).toBeVisible();

	// Counted events, not sampled points: the cells carry single digits.
	const cells = workouts.locator('span[title*="2026-"]');
	expect(await cells.count()).toBeGreaterThan(100);
	await expect(cells.first()).toHaveAttribute('title', /2026-\d\d-\d\d · \d/);
});

test('narrows every panel, including both heatmaps', async ({ page }) => {
	await page.goto(QUARTER);
	await page.getByRole('link', { name: 'Oura', exact: true }).click();

	await expect(page).toHaveURL(`${QUARTER}&provider=oura`);
	await expect(page.getByRole('link', { name: 'Oura', exact: true })).toHaveAttribute(
		'aria-current',
		'true'
	);

	// Totals and the provider timeline follow the filter.
	const collected = page.getByRole('region').filter({ hasText: 'Data collected' });
	await expect(collected.getByText('7420')).toBeVisible();
	await expect(collected.getByTitle('Oura', { exact: true })).toBeVisible();
	await expect(collected.getByTitle('Garmin', { exact: true })).toHaveCount(0);

	// Series types still plots over time rather than dropping to totals, and
	// carries only what Oura delivers.
	const types = page.getByRole('region').filter({ hasText: 'Series types' });
	await expect(types.locator('span[title*="2026-"]').first()).toBeVisible();
	await expect(types.getByText('Oxygen saturation')).toBeVisible();
	await expect(types.getByText('Steps')).toHaveCount(0);

	// And the workout heatmap narrows with them, which is what the summary's
	// per-provider counts could never answer.
	const workouts = page.getByRole('region').filter({ hasText: 'Workout types' });
	await expect(workouts.getByText('Swimming')).toBeVisible();
	await expect(workouts.getByText('Running')).toHaveCount(0);
});

test('keeps the chosen provider when the period changes', async ({ page }) => {
	await page.goto(QUARTER);
	await page.getByRole('link', { name: 'Oura', exact: true }).click();

	// Wait for it to land: the period link's href is built from the current URL,
	// so clicking mid-flight would carry a URL that has no provider in it yet —
	// which is a race in the test, not in the page.
	await expect(page).toHaveURL(`${QUARTER}&provider=oura`);

	await page.getByRole('link', { name: 'All time' }).click();

	await expect(page).toHaveURL(`${DATA}?provider=oura`);
	await expect(page.getByRole('link', { name: 'Oura', exact: true })).toHaveAttribute(
		'aria-current',
		'true'
	);
});

test('drops a provider the user is not connected to rather than failing', async ({ page }) => {
	// The API takes an enum, so an invented slug would 422 every timeline.
	await page.goto(`${QUARTER}&provider=nonsense`);

	await expect(page.getByText('Everything stored for this user')).toBeVisible();
	await expect(page.getByRole('link', { name: 'All', exact: true })).toHaveAttribute(
		'aria-current',
		'true'
	);
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

	// Workout types falls back the same way, through the same component.
	const workouts = page.getByRole('region').filter({ hasText: 'Workout types' });
	await expect(workouts.getByText('Workouts recorded that day')).toBeVisible();
	await expect(workouts.getByText('Running')).toBeVisible();
});
