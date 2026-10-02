import { expect, type Locator, type Page } from '@playwright/test';
import { CREDENTIALS } from './fixtures';

export async function signIn(page: Page): Promise<void> {
	await page.goto('/login');
	await page.getByLabel('Email').fill(CREDENTIALS.email);
	await page.getByLabel('Password').fill(CREDENTIALS.password);
	await page.getByRole('button', { name: 'Sign in' }).click();

	// Longer than the default five seconds, and deliberately: this one assertion
	// spans the login POST, a session written to Redis, the redirect, and the
	// dashboard's own three requests. It used to resolve on a static placeholder.
	// A login that is actually broken still fails, just later.
	await expect(page).toHaveURL('/dashboard', { timeout: 20_000 });
}

/** The list carries the same bar above and below; tests drive the lower one. */
export function pager(page: Page): Locator {
	return page.getByRole('navigation', { name: 'Pagination below the list' });
}
