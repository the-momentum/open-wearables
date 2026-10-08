import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const UNCONNECTED = '00000000-0000-4000-8000-000000000003';
const CYCLES = `/users/${USER}/womens-health`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('lists cycles newest first, with the one running now marked', async ({ page }) => {
	await page.goto(CYCLES);

	// The forecast comes first, because it starts after the cycle running now.
	const cards = page.getByRole('article');
	await expect(cards.first()).toContainText('Predicted');

	// The running cycle says where it stands; a closed one has no today to mark.
	await expect(cards.nth(1)).toContainText('Day 13 today');
	await expect(cards.nth(2)).toContainText('Luteal');
	await expect(cards.nth(2)).not.toContainText('today');
});

test('draws the phases across the cycle, on one scale for the whole page', async ({ page }) => {
	await page.goto(CYCLES);

	const running = page.getByRole('article').nth(1);
	// Titles rather than text: the bar is colour, and this is what it means.
	await expect(running.getByTitle(/^Period: day 1–4$/)).toBeVisible();
	await expect(running.getByTitle(/^Fertile: day 8–13$/)).toBeVisible();
	await expect(running.getByTitle(/^Luteal: day 14–26$/)).toBeVisible();

	// A twenty-six day cycle must not fill the same width as a thirty day one,
	// so the widths are a share of the longest cycle on the page.
	const width = (card: number) =>
		page
			.getByRole('article')
			.nth(card)
			.locator('[title^="Luteal"]')
			.evaluate((node) => Number(node.style.left.replace('%', '')));

	expect(await width(1)).not.toBe(await width(4));
});

test('opens a cycle for what the bar cannot say', async ({ page }) => {
	await page.goto(CYCLES);

	const card = page.getByRole('article').nth(1);
	await card.getByRole('button').first().click();

	await expect(card.getByText('Day 8–13')).toBeVisible();
	await expect(card.getByText('Fertile window')).toBeVisible();
	// The difference between a record and an estimate is worth a word.
	await expect(card.getByText('Estimated')).toBeVisible();
	await expect(card.getByText('Predicted length')).toHaveCount(0);
});

test('averages the cycles that were lived, not the forecast', async ({ page }) => {
	await page.goto(CYCLES);

	const figures = page.locator('[aria-label="Cycle totals"]');
	await expect(figures.getByText('Avg cycle')).toBeVisible();
	// Lengths run 26 to 30, so the mean sits inside that range rather than being
	// dragged by the twenty-eight day prediction.
	await expect(figures.getByText(/^2[6-9](\.\d)? days$/)).toBeVisible();
});

test('deletes a cycle after confirming, and the list agrees afterwards', async ({ page }) => {
	await page.goto(CYCLES);

	const card = page.getByRole('article').nth(1);
	await card.getByRole('button').first().click();
	await card.getByRole('button', { name: 'Delete cycle' }).click();

	await page
		.getByRole('dialog', { name: 'Delete cycle?' })
		.getByRole('button', { name: 'Delete' })
		.click();

	await expect(page.getByRole('article').nth(1)).not.toContainText('Day 13 today');
});

test('pages back through a year of cycles', async ({ page }) => {
	await page.goto(CYCLES);
	await expect(page.getByRole('article')).toHaveCount(10);

	await page.getByRole('link', { name: 'Next page' }).click();
	await expect(page.getByRole('article')).toHaveCount(5);
	await expect(page.getByRole('navigation', { name: 'Pagination' })).toContainText('of 15');
});

test('says so when the user has no cycles at all', async ({ page }) => {
	await page.goto(`/users/${UNCONNECTED}/womens-health`);

	await expect(page.getByText('No cycles recorded')).toBeVisible();
	await expect(page.getByRole('article')).toHaveCount(0);
});
