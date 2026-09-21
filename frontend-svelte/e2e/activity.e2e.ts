import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const ACTIVITY = `/users/${USER}/activity`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('lists one row a day, newest first, and says where the row came from', async ({ page }) => {
	await page.goto(ACTIVITY);

	const cards = page.getByRole('article');
	await expect(cards).toHaveCount(10);

	// A weekday tells an admin more than a date alone: "nothing on Sundays" is a
	// pattern, "nothing on the 14th" is not.
	await expect(cards.first().getByRole('heading')).toContainText('Monday');
	await expect(cards.first().getByRole('heading')).toContainText('21 Sept 2026');

	// The endpoint picks the winning source per date, so the card names the one it
	// used rather than offering a filter that does not exist.
	await expect(page.getByRole('group', { name: 'Provider' })).toHaveCount(0);
	await expect(page.getByText('whichever source ranks highest')).toBeVisible();
	await expect(cards.first()).toContainText('Oura');
});

test('sums the whole period beside the list, averaging over the days that reported', async ({
	page
}) => {
	await page.goto(ACTIVITY);

	// Three of the 24 days are gaps, which is what makes the average worth having.
	const figures = page.locator('[aria-label="Activity totals"]');
	await expect(figures.getByText('21', { exact: true })).toBeVisible();
	await expect(figures.getByText('Avg steps a day')).toBeVisible();
});

test('pages on without claiming a last page the endpoint never counted', async ({ page }) => {
	await page.goto(ACTIVITY);
	const pager = page.getByRole('navigation', { name: 'Pagination' });

	// This endpoint builds its Pagination without a total, so there is no "of N"
	// to show — and showing "of 1" beside a working next arrow is worse than
	// showing nothing.
	await expect(pager).toContainText('1–10');
	await expect(pager).not.toContainText('of 1');

	await pager.getByRole('link', { name: 'Next page' }).click();
	await expect(pager).toContainText('11–20');

	await pager.getByRole('link', { name: 'Previous page' }).click();
	await expect(page).toHaveURL(ACTIVITY);
});

test('draws the readings through the day, and only once a row is opened', async ({ page }) => {
	const calls: string[] = [];
	page.on('request', (request) => {
		if (request.url().includes('/activity/samples')) calls.push(request.url());
	});

	await page.goto(ACTIVITY);
	expect(calls).toEqual([]);

	const card = page.getByRole('article').first();
	await card.getByText('Steps').click();

	const chart = card.getByRole('img', { name: 'Readings across the day' });
	await expect(chart).toBeVisible();
	expect(calls).toHaveLength(1);

	// Steps and heart rate, each its own line — and no daily totals towering over
	// them, which share this endpoint in raw mode.
	await expect(card.getByRole('button', { name: 'Steps' })).toBeVisible();
	await expect(card.getByRole('button', { name: 'Heart rate' })).toBeVisible();
});

test('leaves out a detail group the provider had nothing for', async ({ page }) => {
	await page.goto(ACTIVITY);

	// Garmin sends intensity bands, Oura does not, and the first row is Oura's.
	const oura = page.getByRole('article').first();
	await oura.getByText('Steps').click();
	await expect(oura.getByText('MOVEMENT')).toBeVisible();
	await expect(oura.getByText('INTENSITY')).toHaveCount(0);

	const garmin = page.getByRole('article').filter({ hasText: 'Garmin' }).first();
	await garmin.getByText('Steps').click();
	await expect(garmin.getByText('INTENSITY')).toBeVisible();
});
