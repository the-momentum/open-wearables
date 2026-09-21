import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const SLEEP = `/users/${USER}/sleep`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('lists sessions newest first, dated by the morning they ended', async ({ page }) => {
	await page.goto(SLEEP);

	const cards = page.getByRole('article');
	await expect(cards).toHaveCount(10);

	// The kind titles the card, as the type does on a workout, and the day it was
	// woken up in sits under it — which is how anyone looks for "last night".
	const first = cards.first().getByRole('heading');
	await expect(first).toContainText('Night sleep');
	await expect(first).toContainText('Mon, 21 Sept 2026');
	// Bedtime and wake time read as two times, not as one grey run of characters.
	await expect(first).toContainText('00:40');
	await expect(first).toContainText('08:20');

	const pager = page.getByRole('navigation', { name: 'Pagination' });
	await expect(pager).toContainText('1–10 of 17');

	// Naps are sessions too, and the title is where that shows.
	await expect(cards.filter({ hasText: 'Nap' }).first()).toBeVisible();

	// The fourth slot is the whole stage mix, not one stage promoted above the
	// others: four segments, each naming itself.
	await expect(cards.first().getByTitle(/^Deep · /)).toBeVisible();
	await expect(cards.first().getByTitle(/^REM · /)).toBeVisible();
});

test('sums the whole period beside the list, not the page in front of you', async ({ page }) => {
	await page.goto(SLEEP);

	const figures = page.locator('[aria-label="Sleep totals"]');
	await expect(figures.getByText('17', { exact: true })).toBeVisible();
	await expect(figures.getByText('Avg efficiency')).toBeVisible();
});

test('draws the stages through the night where the provider sent intervals', async ({ page }) => {
	await page.goto(SLEEP);

	// Oura reports intervals, so its card gets a lane per stage.
	const oura = page.getByRole('article').filter({ hasText: 'Oura' }).first();
	await oura.getByText('Asleep').click();

	const lanes = oura.getByRole('img', { name: 'Sleep stages across the session' });
	await expect(lanes).toBeVisible();
	await expect(lanes.getByText('Deep')).toBeVisible();
	await expect(lanes.getByText('REM')).toBeVisible();

	// And the strip below counts the same stages, from the minute totals.
	await expect(oura.getByText('Time in each stage')).toBeVisible();
});

test('says so when a provider reports stage minutes but not when they happened', async ({
	page
}) => {
	await page.goto(SLEEP);

	// Suunto sends the per-stage minutes and no intervals: the strip is there, the
	// hypnogram cannot be, and a bare gap would read as missing data.
	const suunto = page.getByRole('article').filter({ hasText: 'Suunto' }).first();
	await suunto.getByText('Asleep').click();

	await expect(suunto.getByText('but not when')).toBeVisible();
	await expect(suunto.getByRole('img', { name: 'Sleep stages across the session' })).toHaveCount(0);
	await expect(suunto.getByText('Time in each stage')).toBeVisible();
});

test('keeps only the winning source per night when asked', async ({ page }) => {
	await page.goto(SLEEP);
	await expect(page.getByRole('article').filter({ hasText: 'Suunto' }).first()).toBeVisible();

	// Two watches can both claim one night; this is the ranking summaries use.
	await page.getByRole('link', { name: 'Highest priority' }).click();

	await expect(page).toHaveURL(`${SLEEP}?top=1`);
	await expect(page.getByRole('article').filter({ hasText: 'Suunto' })).toHaveCount(0);
	await expect(page.getByRole('article').first()).toContainText('Oura');
});

test('deletes a session after confirming, and the list agrees afterwards', async ({ page }) => {
	await page.goto(SLEEP);
	const pager = page.getByRole('navigation', { name: 'Pagination' });
	await expect(pager).toContainText('of 17');

	await page.getByRole('article').first().getByRole('button').first().click();
	await page.getByRole('button', { name: 'Delete session' }).click();
	await page.getByRole('button', { name: 'Delete', exact: true }).click();

	await expect(pager).toContainText('of 16');
});
