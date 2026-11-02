import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const MEALS = `/users/${USER}/meals`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('is a tab of the user, listing meals newest first with calories and macros', async ({
	page
}) => {
	await page.goto(`/users/${USER}`);
	await page.getByRole('link', { name: 'Meals' }).click();
	await expect(page).toHaveURL(new RegExp(`${MEALS}$`));

	const cards = page.getByRole('article');
	await expect(cards).toHaveCount(10);

	// A snack logged without a food name is titled by its type.
	const first = cards.first();
	await expect(first.getByRole('heading')).toContainText('Snack');
	await expect(first).toContainText('210 kcal');
	await expect(first).toContainText('20 g');
	await expect(cards.nth(1).getByRole('heading')).toContainText('Chicken salad');
});

test('opens a meal for every nutrient it carries, grouped and with units', async ({ page }) => {
	await page.goto(MEALS);

	const card = page.getByRole('article').nth(1);
	await card.getByRole('button').first().click();

	await expect(card.getByText('Energy from macros')).toBeVisible();
	await expect(card.getByText('Minerals')).toBeVisible();
	await expect(card.getByText('380 mg')).toBeVisible();
	await expect(card.getByText('Vitamin C')).toBeVisible();
	await expect(card.getByText('12.5 mg')).toBeVisible();
});

test('sums the period, not just the page', async ({ page }) => {
	await page.goto(MEALS);

	const figures = page.locator('[aria-label="Meal totals"]');
	await expect(figures.getByText('21', { exact: true })).toBeVisible();
});

test('deletes a meal after confirming, and the list agrees afterwards', async ({ page }) => {
	await page.goto(MEALS);

	const card = page.getByRole('article').nth(1);
	await card.getByRole('button').first().click();
	await card.getByRole('button', { name: 'Delete meal' }).click();

	await page
		.getByRole('dialog', { name: 'Delete meal?' })
		.getByRole('button', { name: 'Delete' })
		.click();

	await expect(
		page.locator('[aria-label="Meal totals"]').getByText('20', { exact: true })
	).toBeVisible();
});
