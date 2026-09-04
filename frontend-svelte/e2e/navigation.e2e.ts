import { expect, test } from '@playwright/test';
import { signIn } from './support';

// Every destination now sits behind the auth guard.
test.beforeEach(async ({ page }) => {
	await signIn(page);
});

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 800 };

test('sends the root path to the dashboard', async ({ page }) => {
	await page.goto('/');
	await expect(page).toHaveURL('/dashboard');
});

test.describe('desktop', () => {
	test.use({ viewport: DESKTOP });

	test('navigates from the sidebar and hides the mobile bar', async ({ page }) => {
		await page.goto('/dashboard');

		const sidebar = page.getByRole('navigation', { name: 'Main' });
		await expect(sidebar).toBeVisible();
		await expect(page.getByRole('navigation', { name: 'Primary' })).toBeHidden();

		await sidebar.getByRole('link', { name: 'Users' }).click();

		await expect(page).toHaveURL('/users');
		await expect(sidebar.getByRole('link', { name: 'Users' })).toHaveAttribute(
			'aria-current',
			'page'
		);
	});

	test('shows the package version, not SvelteKit’s build timestamp', async ({ page }) => {
		await page.goto('/dashboard');

		await expect(page.getByRole('complementary').getByText(/^\d+\.\d+\.\d+$/)).toBeVisible();
	});
});

test.describe('mobile', () => {
	test.use({ viewport: MOBILE });

	test('navigates from the bottom bar and hides the sidebar', async ({ page }) => {
		await page.goto('/dashboard');

		const bottomNav = page.getByRole('navigation', { name: 'Primary' });
		await expect(bottomNav).toBeVisible();
		await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden();

		await bottomNav.getByRole('link', { name: 'Syncs' }).click();

		await expect(page).toHaveURL('/syncs');
	});

	test('reaches a secondary destination through the More sheet and closes it', async ({ page }) => {
		await page.goto('/dashboard');

		const more = page.getByRole('button', { name: 'More' });
		await more.click();

		const sheet = page.getByRole('dialog', { name: 'More' });
		await expect(sheet).toBeVisible();

		await sheet.getByRole('link', { name: 'Settings' }).click();

		await expect(page).toHaveURL('/settings');
		await expect(sheet).toBeHidden();
	});

	test('keeps logout and the version reachable, since the sidebar is desktop-only', async ({
		page
	}) => {
		await page.goto('/dashboard');
		await page.getByRole('button', { name: 'More' }).click();

		const sheet = page.getByRole('dialog', { name: 'More' });
		await expect(sheet.getByRole('button', { name: 'Logout' })).toBeVisible();
		await expect(sheet.getByText(/^\d+\.\d+\.\d+$/)).toBeVisible();
	});

	test('closes the More sheet with Escape', async ({ page }) => {
		await page.goto('/dashboard');
		await page.getByRole('button', { name: 'More' }).click();

		const sheet = page.getByRole('dialog', { name: 'More' });
		await expect(sheet).toBeVisible();

		await page.keyboard.press('Escape');

		await expect(sheet).toBeHidden();
	});

	test('content clears the fixed bottom bar', async ({ page }) => {
		await page.goto('/dashboard');

		const contentBottom = await page
			.getByRole('main')
			.evaluate((el) => el.getBoundingClientRect().bottom);
		const navTop = await page
			.getByRole('navigation', { name: 'Primary' })
			.evaluate((el) => el.getBoundingClientRect().top);

		expect(contentBottom).toBeLessThanOrEqual(navTop);
	});
});
