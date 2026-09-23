import { expect, test } from '@playwright/test';
import { signIn } from './support';

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('says which account you are signed in as, on every page', async ({ page }) => {
	await page.goto('/dashboard');

	// It was answerable nowhere before: the sidebar carries it beside the way out.
	// Both layouts render at once, so this names the one it is asking about.
	await expect(page.getByRole('complementary')).toContainText('dev@example.com');
});

test('shows the key prefix but never a whole key until one is minted', async ({ page }) => {
	await page.goto('/settings');

	await expect(page.getByText('ow_live_9f2a…')).toBeVisible();
	await expect(page.getByText('ow_live_new1_full_secret_value')).toHaveCount(0);

	await page.getByRole('button', { name: 'New key' }).click();
	await page.getByRole('dialog').getByLabel('Name', { exact: true }).fill('CI runner');
	await page.getByRole('button', { name: 'Create key' }).click();

	// The one and only showing: the API stores a hash, so a reload cannot repeat it.
	await expect(page.getByRole('dialog')).toContainText('API key created');
	await expect(page.getByRole('dialog').getByLabel('CI runner', { exact: true })).toHaveValue(
		'ow_live_new1_full_secret_value'
	);
});

test('rotates a key and shows the replacement once', async ({ page }) => {
	await page.goto('/settings');

	await page.getByRole('button', { name: 'Rotate Production backend' }).click();
	await page.getByRole('button', { name: 'Rotate key' }).click();

	await expect(page.getByRole('dialog')).toContainText('API key rotated');
	await expect(
		page.getByRole('dialog').getByLabel('Production backend', { exact: true })
	).toHaveValue('ow_live_rot8_full_secret_value');
});

test('renames a key without minting a new one', async ({ page }) => {
	await page.goto('/settings');

	await page.getByRole('button', { name: 'Rename Production backend' }).click();
	await page.getByRole('dialog').getByLabel('Name', { exact: true }).fill('Renamed key');
	await page.getByRole('button', { name: 'Save changes' }).click();

	await expect(page.getByText('Renamed key')).toBeVisible();
	await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('hands over both halves of an SDK application, and only once', async ({ page }) => {
	await page.goto('/settings');

	await page.getByRole('button', { name: 'New application' }).click();
	await page
		.getByRole('dialog')
		.getByLabel('Application name', { exact: true })
		.fill('Android beta');
	await page.getByRole('button', { name: 'Create application' }).click();

	const reveal = page.getByRole('dialog');
	await expect(reveal.getByLabel('App ID', { exact: true })).toHaveValue(/^app_/);
	await expect(reveal.getByLabel('App secret', { exact: true })).toHaveValue(
		'app_secret_shown_once'
	);
});

test('deletes an API key after confirming', async ({ page }) => {
	await page.goto('/settings');

	await page.getByRole('button', { name: 'Delete Production backend' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click();

	// Asserted on the prefix, not the name: the dialog that just closed still
	// carries the name in the warning it showed.
	await expect(page.getByText('ow_live_9f2a…')).toHaveCount(0);
	await expect(page.getByText('No API keys yet')).toBeVisible();
});

test('holds provider switches as a draft until they are saved', async ({ page }) => {
	await page.goto('/settings/providers');

	const whoop = page.getByRole('switch', { name: 'Enable Whoop' });
	await expect(whoop).toHaveAttribute('aria-checked', 'false');

	await whoop.click();
	// Nothing is sent yet: disabling a provider by accident takes it off the
	// pairing page for everyone, so the draft waits for a deliberate save.
	await expect(page.getByText('1 provider changed')).toBeVisible();

	await page.getByRole('button', { name: 'Save changes' }).click();
	await expect(page.getByText('provider changed')).toHaveCount(0);

	await page.reload();
	await expect(page.getByRole('switch', { name: 'Enable Whoop' })).toHaveAttribute(
		'aria-checked',
		'true'
	);
});

test('switches one provider to webhooks on the click, without a save', async ({ page }) => {
	await page.goto('/settings/providers');

	const oura = page.getByRole('group', { name: 'How Oura reports new data' });
	await expect(oura.getByRole('button', { name: 'Periodic pull' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);

	await oura.getByRole('button', { name: 'Webhook' }).click();
	await expect(oura.getByRole('button', { name: 'Webhook' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	// One provider's own setting, so no draft appears for it.
	await expect(page.getByText('provider changed')).toHaveCount(0);
});

test('states the mode as a fact where the provider offers no choice', async ({ page }) => {
	await page.goto('/settings/providers');

	await expect(page.getByText('Webhook only')).toBeVisible();
	await expect(page.getByRole('group', { name: 'How Garmin reports new data' })).toHaveCount(0);
});

test('reorders providers and keeps the order after saving', async ({ page }) => {
	await page.goto('/settings/priorities');

	const list = page.getByRole('list', { name: 'Provider priority' });
	await expect(list.getByRole('listitem').first()).toContainText('Garmin');

	await list.getByRole('button', { name: 'Move oura up' }).click();
	await expect(list.getByRole('listitem').first()).toContainText('Oura');

	await page.getByRole('button', { name: 'Save changes' }).click();
	await page.reload();

	await expect(
		page.getByRole('list', { name: 'Provider priority' }).getByRole('listitem').first()
	).toContainText('Oura');
});

test('cannot move the top row up or the bottom row down', async ({ page }) => {
	await page.goto('/settings/priorities');

	const list = page.getByRole('list', { name: 'Device priority' });
	await expect(list.getByRole('button', { name: 'Move watch up' })).toBeDisabled();
	await expect(list.getByRole('button', { name: 'Move phone down' })).toBeDisabled();
});

test('lists the team, marking the account you are signed in as', async ({ page }) => {
	await page.goto('/settings/team');

	await expect(page.getByText('colleague@example.com').first()).toBeVisible();
	await expect(page.getByText('You', { exact: true })).toBeVisible();

	// Nobody can remove themselves, so that row offers the password instead.
	await expect(page.getByRole('button', { name: 'Remove dev@example.com' })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Change password' })).toBeVisible();
});

test('shows only the invitations still worth acting on', async ({ page }) => {
	await page.goto('/settings/team');

	await expect(page.getByText('new.hire@example.com')).toBeVisible();
	// Lapsed and already accepted are not things to chase.
	await expect(page.getByText('never.replied@example.com')).toHaveCount(0);
	await expect(page.getByText('Pending invitations')).toBeVisible();
});

test('invites someone, and says so when they are already on the team', async ({ page }) => {
	await page.goto('/settings/team');

	await page.getByRole('button', { name: 'Invite', exact: true }).click();
	const invite = page.getByRole('dialog');
	await invite.getByLabel('Email address', { exact: true }).fill('colleague@example.com');
	await invite.getByRole('button', { name: 'Send invitation' }).click();
	await expect(page.getByRole('alert')).toBeVisible();

	await invite.getByLabel('Email address', { exact: true }).fill('fresh@example.com');
	await invite.getByRole('button', { name: 'Send invitation' }).click();
	await expect(page.getByText('fresh@example.com')).toBeVisible();
});

test('revokes an invitation after confirming', async ({ page }) => {
	await page.goto('/settings/team');

	await page.getByRole('button', { name: 'Revoke invitation for new.hire@example.com' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Revoke' }).click();

	// It was the only one worth chasing, so the whole section goes with it.
	await expect(page.getByText('Pending invitations')).toHaveCount(0);
});

test('changes your password from your own row, and rejects a wrong current one', async ({
	page
}) => {
	await page.goto('/settings/team');

	await page.getByRole('button', { name: 'Change password' }).click();
	const dialog = page.getByRole('dialog');
	await dialog.getByLabel('Current password', { exact: true }).fill('wrong-password');
	await dialog.getByLabel('New password', { exact: true }).fill('a-longer-password');
	await dialog.getByLabel('Confirm new password', { exact: true }).fill('a-longer-password');
	await page.getByRole('button', { name: 'Update password' }).click();
	await expect(page.getByRole('alert')).toContainText('Incorrect current password');

	await dialog.getByLabel('Current password', { exact: true }).fill('correct-horse');
	await page.getByRole('button', { name: 'Update password' }).click();
	await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('catches a mismatched confirmation before sending it anywhere', async ({ page }) => {
	await page.goto('/settings/team');

	await page.getByRole('button', { name: 'Change password' }).click();
	const dialog = page.getByRole('dialog');
	await dialog.getByLabel('Current password', { exact: true }).fill('correct-horse');
	await dialog.getByLabel('New password', { exact: true }).fill('a-longer-password');
	await dialog.getByLabel('Confirm new password', { exact: true }).fill('a-different-password');
	await page.getByRole('button', { name: 'Update password' }).click();

	// FastAPI answers a mismatch with a validation array and no `detail`, which
	// would reach the reader as nothing at all.
	await expect(page.getByRole('alert')).toContainText('does not match');
});

test('marks Data Lifecycle as beta, in words on a desktop and as a mark on a phone', async ({
	page
}) => {
	await page.goto('/settings');

	const tab = page.getByRole('link', { name: /Data Lifecycle/ });
	await expect(tab).toContainText('Beta');

	await page.setViewportSize({ width: 390, height: 844 });
	// The word costs a tab's width on a phone, so the mark rides the icon — the
	// same trade the bottom bar makes for Webhooks.
	await expect(tab.getByText('Beta', { exact: true })).toBeHidden();
	await expect(tab).toContainText('β');
});

test('keeps every settings tab inside the viewport on a phone', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });

	for (const path of [
		'/settings',
		'/settings/providers',
		'/settings/priorities',
		'/settings/team'
	]) {
		await page.goto(path);
		const width = await page.evaluate(() => document.documentElement.scrollWidth);
		expect(width, path).toBeLessThanOrEqual(390);
	}
});
