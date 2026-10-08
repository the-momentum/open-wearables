import { expect, test, type Page } from '@playwright/test';
import { CREDENTIALS, DEFAULT_PASSWORD } from './fixtures';

test.beforeEach(async ({ request }) => {
	await request.post('http://localhost:8787/__reset');
});

async function signInWithDefault(page: Page) {
	await page.goto('/login');
	await page.getByLabel('Email').fill(CREDENTIALS.email);
	await page.getByLabel('Password').fill(DEFAULT_PASSWORD);
	await page.getByRole('button', { name: 'Sign in' }).click();
	await expect(page).toHaveURL('/change-password', { timeout: 20_000 });
}

test('keeps a production portal on the prompt until the password changes', async ({ page }) => {
	await signInWithDefault(page);
	await expect(page.getByRole('button', { name: 'Not now' })).toHaveCount(0);

	await page.goto('/dashboard');
	await expect(page).toHaveURL('/change-password');

	await page.getByLabel('Current password', { exact: true }).fill(DEFAULT_PASSWORD);
	await page.getByLabel('New password', { exact: true }).fill('a-much-better-one');
	await page.getByLabel('Confirm new password', { exact: true }).fill('a-much-better-one');
	await page.getByRole('button', { name: 'Update password' }).click();

	await expect(page).toHaveURL('/dashboard', { timeout: 20_000 });
	await page.goto('/change-password');
	await expect(page).toHaveURL('/dashboard');
});

test('rejects a confirmation that does not match', async ({ page }) => {
	await signInWithDefault(page);

	await page.getByLabel('Current password', { exact: true }).fill(DEFAULT_PASSWORD);
	await page.getByLabel('New password', { exact: true }).fill('a-much-better-one');
	await page.getByLabel('Confirm new password', { exact: true }).fill('something-else');
	await page.getByRole('button', { name: 'Update password' }).click();

	await expect(page.getByRole('alert')).toContainText('does not match');
	await expect(page).toHaveURL('/change-password');
});

test('lets a local stack skip the prompt', async ({ page, request }) => {
	await request.post('http://localhost:8787/__not-production');
	await signInWithDefault(page);

	await page.getByRole('button', { name: 'Not now' }).click();
	await expect(page).toHaveURL('/dashboard', { timeout: 20_000 });
});

test('does not prompt an account with its own password', async ({ page }) => {
	await page.goto('/login');
	await page.getByLabel('Email').fill(CREDENTIALS.email);
	await page.getByLabel('Password').fill(CREDENTIALS.password);
	await page.getByRole('button', { name: 'Sign in' }).click();
	await expect(page).toHaveURL('/dashboard', { timeout: 20_000 });

	await page.goto('/change-password');
	await expect(page).toHaveURL('/dashboard');
});
