import { expect, type Locator, type Page } from '@playwright/test';
import { CREDENTIALS } from './fixtures';

export async function signIn(page: Page): Promise<void> {
	await page.goto('/login');
	await page.getByLabel('Email').fill(CREDENTIALS.email);
	await page.getByLabel('Password').fill(CREDENTIALS.password);
	await page.getByRole('button', { name: 'Sign in' }).click();
	await expect(page).toHaveURL('/dashboard');
}

/** The list carries the same bar above and below; tests drive the lower one. */
export function pager(page: Page): Locator {
	return page.getByRole('navigation', { name: 'Pagination below the list' });
}
