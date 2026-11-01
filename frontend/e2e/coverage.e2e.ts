import { expect, test } from '@playwright/test';
import { signIn } from './support';

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('names the providers on every row instead of a grid of dots', async ({ page }) => {
	await page.goto('/coverage');

	// Fourteen columns of dots have to scroll sideways on a phone, and a reader
	// still has to look up which column is which. The supporters sit on the row.
	const row = page.getByText('heart_rate', { exact: true }).locator('..').locator('..');
	await expect(row.getByTitle('Garmin')).toBeVisible();
	await expect(row.getByTitle('Oura')).toBeVisible();
	await expect(row).toContainText('3 of 4');
});

test('calls out a capability only one provider can deliver', async ({ page }) => {
	await page.goto('/coverage');

	// Dropping that integration loses this outright, which a dot in a grid never
	// said out loud.
	const row = page.getByText('bone_mass', { exact: true }).locator('..').locator('..');
	await expect(row.getByText('only')).toBeVisible();
	await expect(row).toContainText('1 of 4');
});

test('ranks the providers by how much of the matrix they cover', async ({ page }) => {
	await page.goto('/coverage');

	const summary = page.getByRole('region', { name: 'What each provider can deliver' });
	// Garmin is in every row of the fixture: 9 of 9.
	await expect(summary.getByText('9 · 100%')).toBeVisible();
	await expect(summary.getByText('Garmin')).toBeVisible();
});

test('searches across every layer at once', async ({ page }) => {
	await page.goto('/coverage');
	await expect(page.getByText('9 of 9 capabilities · 4 providers')).toBeVisible();

	await page.getByLabel('Search capabilities').fill('heart');
	await expect(page).toHaveURL(/search=heart/);
	await expect(page.getByText('2 of 9 capabilities')).toBeVisible();
	await expect(page.getByText('average_cadence')).toHaveCount(0);
});

test('narrows to one layer', async ({ page }) => {
	await page.goto('/coverage');

	await page
		.getByRole('group', { name: 'Layer' })
		.getByRole('link', { name: 'Sleep fields' })
		.click();

	await expect(page).toHaveURL(/layer=sleep/);
	await expect(page.getByText('deep_sleep_seconds')).toBeVisible();
	await expect(page.getByText('heart_rate', { exact: true })).toHaveCount(0);
});

test('asks what a provider cannot deliver, not only what it can', async ({ page }) => {
	await page.goto('/coverage?provider=whoop');

	await expect(page.getByText('total_distance')).toBeVisible();
	await expect(page.getByText('average_cadence')).toHaveCount(0);

	// The half of the question the old matrix could not be asked.
	await page.getByRole('group', { name: 'Side' }).getByRole('link', { name: 'Cannot' }).click();

	await expect(page).toHaveURL(/missing=1/);
	await expect(page.getByText('average_cadence')).toBeVisible();
	await expect(page.getByText('total_distance')).toHaveCount(0);
});

test('drops a provider the matrix has never heard of', async ({ page }) => {
	await page.goto('/coverage?provider=invented');

	// The whole matrix, not an empty page that reads as a bug.
	await expect(page.getByText('9 of 9 capabilities')).toBeVisible();
	await expect(page.getByRole('group', { name: 'Side' })).toHaveCount(0);
});

test('says so when nothing matches', async ({ page }) => {
	await page.goto('/coverage?search=zzzz');

	await expect(page.getByText('Nothing matches')).toBeVisible();
});
