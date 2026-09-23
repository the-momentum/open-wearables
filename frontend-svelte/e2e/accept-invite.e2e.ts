import { expect, test, type Page } from '@playwright/test';
import { CREDENTIALS } from './fixtures';
import { signIn } from './support';

test.beforeEach(async ({ request }) => {
	await request.post('http://localhost:8787/__reset');
});

async function join(
	page: Page,
	token: string,
	password = CREDENTIALS.password,
	confirm = password
) {
	await page.goto(`/accept-invite?token=${token}`);
	await page.getByLabel('First name').fill('Ada');
	await page.getByLabel('Last name').fill('Lovelace');
	await page.getByLabel('Password', { exact: true }).fill(password);
	await page.getByLabel('Confirm password', { exact: true }).fill(confirm);
	await page.getByRole('button', { name: 'Join the team' }).click();
}

// The backend writes this exact path and parameter into every invitation email.
test('accepts the invitation and signs straight in', async ({ page }) => {
	await join(page, 'invite-ok');
	await expect(page).toHaveURL('/dashboard', { timeout: 20_000 });
});

// The account exists by then, so a failed sign-in is a detour, not an error.
test('points to sign-in when it cannot sign the new account in itself', async ({ page }) => {
	await join(page, 'invite-new');
	await expect(page.getByRole('heading', { name: 'Your account is ready' })).toBeVisible();
	await expect(page.getByText('Sign in as ada@example.com')).toBeVisible();
	await page.getByRole('link', { name: 'Sign in' }).click();
	await expect(page).toHaveURL('/login');
});

test('catches a short or mistyped password before the API is asked', async ({ page }) => {
	await join(page, 'invite-ok', 'short');
	await expect(page.getByRole('alert')).toHaveText('The password must be at least 8 characters.');
	await expect(page.getByLabel('First name')).toHaveValue('Ada');

	await join(page, 'invite-ok', 'long-enough-1', 'long-enough-2');
	await expect(page.getByRole('alert')).toHaveText('The confirmation does not match the password.');
});

test('says why a link cannot be used, instead of showing the form again', async ({ page }) => {
	for (const [token, reason] of [
		['nonsense', 'This invitation link is not valid'],
		['invite-expired', 'This invitation has expired'],
		['invite-used', 'This invitation has already been used']
	]) {
		await join(page, token);
		await expect(page.getByRole('heading', { name: reason })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Join the team' })).toHaveCount(0);
	}
});

test('a link with no token is dead before anything is typed', async ({ page }) => {
	await page.goto('/accept-invite');
	await expect(
		page.getByRole('heading', { name: 'This invitation link is not valid' })
	).toBeVisible();
	await page.getByRole('link', { name: 'Sign in' }).click();
	await expect(page).toHaveURL('/login');
});

test('a failure on the server keeps the form, since the link may still be good', async ({
	page
}) => {
	await join(page, 'invite-down');
	await expect(page.getByRole('alert')).toContainText('could not be created');
	await expect(page.getByRole('button', { name: 'Join the team' })).toBeVisible();
});

test('someone already signed in is sent on to the dashboard', async ({ page }) => {
	await signIn(page);
	await page.goto('/accept-invite?token=invite-ok');
	await expect(page).toHaveURL('/dashboard');
});
