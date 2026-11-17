import { expect, test } from '@playwright/test';

const USER = '00000000-0000-4000-8000-000000000007';
const TOKEN = `connect-${USER}`;
const BASE = `/users/${USER}/pair`;
const PAIR = `${BASE}?t=${TOKEN}`;

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

	// The mock hands redirect_uri straight back, so this is what the API received:
	// the token must not be in it, or it lands in the API's request logs.
	await expect(page).toHaveURL(new RegExp(`${BASE}/success\\?provider=garmin&status=success$`));
	await expect(page.getByRole('heading', { name: 'Garmin is connected' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Connect another device' })).toHaveAttribute(
		'href',
		PAIR
	);
});

// The user id alone is not a credential: anyone who learned it could connect their own account.
test('refuses a link without a token', async ({ page }) => {
	await page.goto(BASE);

	await expect(page.getByRole('alert')).toContainText('expired or is invalid');
	await expect(page.getByRole('button', { name: /Garmin/ })).toHaveCount(0);
});

test('refuses a token minted for someone else', async ({ page }) => {
	await page.goto(`${BASE}?t=connect-someone-else`);
	await page.getByRole('button', { name: /Garmin/ }).click();

	await expect(page.getByRole('alert')).toContainText('expired or is invalid');
});

test('reports a provider that cannot be reached instead of a blank page', async ({ page }) => {
	await page.goto(PAIR);
	await page.getByRole('button', { name: /Suunto/ }).click();

	await expect(page.getByRole('alert')).toContainText('Provider credentials are not configured');
	await expect(page.getByRole('button', { name: /Garmin/ })).toBeVisible();
});

// Disabled in Settings, so a user cannot be sent to it at all.
test('offers only the providers that are switched on', async ({ page }) => {
	await page.goto(PAIR);
	await expect(page.getByRole('button', { name: /Garmin/ })).toBeVisible();
	await expect(page.getByRole('button', { name: /Whoop/ })).toHaveCount(0);
});

test('carries a return link through the provider, and only if it is a web address', async ({
	page
}) => {
	await page.goto(`${PAIR}&redirect_url=https%3A%2F%2Fclient.example.com%2Fdone`);
	await page.getByRole('button', { name: /Oura/ }).click();

	await expect(page.getByRole('link', { name: 'Continue' })).toHaveAttribute(
		'href',
		'https://client.example.com/done'
	);
});

// The pairing link is public, so its query string is attacker-controlled.
test('drops a hostile return link rather than rendering it', async ({ page }) => {
	await page.goto(`${PAIR}&redirect_url=javascript%3Aalert(1)`);
	await page.getByRole('button', { name: /Oura/ }).click();

	await expect(page.getByRole('heading', { name: 'Oura is connected' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Continue' })).toHaveCount(0);
});
