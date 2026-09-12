import { expect, test } from '@playwright/test';
import { CREDENTIALS } from './fixtures';
import { signIn } from './support';

test('sends a signed-out visitor to the sign-in page', async ({ page }) => {
	await page.goto('/dashboard');
	await expect(page).toHaveURL('/login');
});

test('rejects wrong credentials without saying which field was wrong', async ({ page }) => {
	await page.goto('/login');
	await page.getByLabel('Email').fill(CREDENTIALS.email);
	await page.getByLabel('Password').fill('not-the-password');
	await page.getByRole('button', { name: 'Sign in' }).click();

	await expect(page.getByRole('alert')).toContainText('Incorrect email or password');
	await expect(page).toHaveURL('/login');
});

test('signs in and reaches the dashboard', async ({ page }) => {
	await signIn(page);
	await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
});

test('keeps the session cookie out of reach of JavaScript', async ({ page, context }) => {
	await signIn(page);

	const cookie = (await context.cookies()).find((c) => c.name === 'ow_session');
	expect(cookie, 'session cookie should exist after signing in').toBeDefined();

	// The reason this design was chosen over localStorage: an XSS cannot read it.
	expect(cookie?.httpOnly).toBe(true);
	expect(cookie?.sameSite).toBe('Lax');

	// And it holds only an opaque id — no token ever reaches the browser.
	expect(cookie?.value).not.toContain('access');
	await expect(page.evaluate(() => document.cookie)).resolves.not.toContain('ow_session');
});

test('signing out ends the session for good', async ({ page }) => {
	await signIn(page);

	await page.getByRole('button', { name: 'Logout' }).click();
	await expect(page).toHaveURL('/login');

	await page.goto('/dashboard');
	await expect(page).toHaveURL('/login');
});

test('sends an already signed-in visitor away from the sign-in page', async ({ page }) => {
	await signIn(page);
	await page.goto('/login');
	await expect(page).toHaveURL('/dashboard');
});
