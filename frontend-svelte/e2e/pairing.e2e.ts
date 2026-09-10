import { expect, test } from '@playwright/test';

const USER = '00000000-0000-4000-8000-000000000007';
const PAIR = `/users/${USER}/pair`;

// No signIn(): whoever opens a pairing link has no account here, and a page
// that only works for a signed-in admin would be useless.
test('opens for someone with no session at all', async ({ page }) => {
	await page.goto(PAIR);

	await expect(page.getByRole('heading', { name: 'Connect a device' })).toBeVisible();
	await expect(page.getByRole('button', { name: /Garmin/ })).toBeVisible();
	await expect(page).toHaveURL(PAIR);
});

test('walks the provider round trip and names what connected', async ({ page }) => {
	await page.goto(PAIR);
	await page.getByRole('button', { name: /Garmin/ }).click();

	await expect(page).toHaveURL(new RegExp(`${PAIR}/success\\?provider=garmin$`));
	await expect(page.getByRole('heading', { name: 'Garmin is connected' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Connect another device' })).toHaveAttribute(
		'href',
		PAIR
	);
});

test('reports a provider that cannot be reached instead of a blank page', async ({ page }) => {
	await page.goto(PAIR);
	await page.getByRole('button', { name: /Whoop/ }).click();

	await expect(page.getByRole('alert')).toContainText('Provider credentials are not configured');
	await expect(page.getByRole('button', { name: /Garmin/ })).toBeVisible();
});

test('carries a return link through the provider, and only if it is a web address', async ({
	page
}) => {
	await page.goto(`${PAIR}?redirect_url=https%3A%2F%2Fclient.example.com%2Fdone`);
	await page.getByRole('button', { name: /Oura/ }).click();

	await expect(page.getByRole('link', { name: 'Continue' })).toHaveAttribute(
		'href',
		'https://client.example.com/done'
	);
});

// The pairing link is public, so its query string is attacker-controlled.
test('drops a hostile return link rather than rendering it', async ({ page }) => {
	await page.goto(`${PAIR}?redirect_url=javascript%3Aalert(1)`);
	await page.getByRole('button', { name: /Oura/ }).click();

	await expect(page.getByRole('heading', { name: 'Oura is connected' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Continue' })).toHaveCount(0);
});
