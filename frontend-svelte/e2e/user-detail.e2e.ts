import { expect, test } from '@playwright/test';
import { signIn } from './support';

/** Has connections, backfills and women's health data. */
const CONNECTED = '00000000-0000-4000-8000-000000000007';
/** Every third fixture user has no connections at all. */
const UNCONNECTED = '00000000-0000-4000-8000-000000000003';

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('shows the stored record and the connection state together', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);

	await expect(page.getByRole('heading', { name: 'Zofia Kowalska' })).toBeVisible();
	await expect(page.getByText('Connected', { exact: true })).toBeVisible();

	// A route that cannot be triggered states itself in place of the control,
	// so a pane is never blank.
	const garmin = page.getByRole('article').filter({ hasText: 'Garmin' });
	await expect(garmin.getByText('Active')).toBeVisible();
	await expect(garmin.getByText('Pushed by the provider', { exact: true })).toBeVisible();

	// Where a control exists, the route moves into its hint — reachable by tap,
	// because hover never fires on a phone.
	await garmin.getByRole('button', { name: 'Historical backfill details' }).click();
	await expect(garmin.getByRole('tooltip').first()).toContainText(
		'Pushed by the provider on demand'
	);
	await expect(garmin.getByRole('tooltip').first()).toContainText('at most 30 days');

	// Scopes are a count beside the name; the list is behind it, not a row.
	await garmin.getByRole('button', { name: '2 granted scopes' }).click();
	const scopes = garmin.getByRole('tooltip').filter({ hasText: 'activity' });
	await expect(scopes).toContainText('activity');
	await expect(scopes).toContainText('sleep');

	// Pinned by tap, so any tap elsewhere has to dismiss it: hunting for the
	// same small target again is not a way out.
	await page.getByRole('heading', { name: 'Connected providers' }).click();
	await expect(scopes).toBeHidden();

	// Same page, a provider configured to pull: the wording must differ, and the
	// two routes share verbs so the pair reads as one story.
	const oura = page.getByRole('article').filter({ hasText: 'Oura' });
	await oura.getByRole('button', { name: 'Live sync details' }).click();
	await expect(oura.getByRole('tooltip').first()).toContainText('Pulled on a schedule');
	await oura.getByRole('button', { name: 'Historical backfill details' }).click();
	await expect(oura.getByText('Pulled on demand')).toBeVisible();
});

test('offers only the sync actions a connection can actually perform', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);

	// Garmin is webhook-driven with a 30-day cap: a backfill is possible, forcing
	// a live pull is not — there is nothing to pull.
	const garmin = page.getByRole('article').filter({ hasText: 'Garmin' });
	await expect(garmin.getByRole('button', { name: 'Sync history' })).toBeVisible();
	await expect(garmin.getByRole('button', { name: 'Sync now' })).toHaveCount(0);

	// Oura has no cap, so the range is the caller's to choose.
	const oura = page.getByRole('article').filter({ hasText: 'Oura' });
	await expect(oura.getByRole('button', { name: 'Sync history' })).toBeVisible();
	await expect(oura.getByLabel('History range')).toHaveValue('90');
	await expect(oura.getByRole('button', { name: 'Sync now' })).toBeVisible();

	// Garmin's backfill ignores the window, so the only truthful option is its
	// cap — the control is still there, ready for the day that changes.
	await expect(garmin.getByLabel('History range')).toHaveValue('30');
	await expect(garmin.getByLabel('History range').locator('option')).toHaveCount(1);

	// An expired connection cannot be told to do anything, and says so in both
	// panes rather than leaving them empty.
	const suunto = page.getByRole('article').filter({ hasText: 'Suunto' });
	await expect(suunto.getByText('Expired')).toBeVisible();
	await expect(suunto.getByRole('button', { name: /^Sync/ })).toHaveCount(0);
	await expect(suunto.getByText('Pushed by the provider', { exact: true })).toBeVisible();
	await expect(suunto.getByText('Pulled on demand')).toBeVisible();
	// Nothing reported, so no badge to open rather than an empty one.
	await expect(suunto.getByRole('button', { name: /granted scopes/ })).toHaveCount(0);
});

test('filters recent activity to one provider without losing the window', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	const recent = page.getByRole('region').filter({ hasText: 'Recent sync activity' });
	await expect(recent.getByRole('listitem')).toHaveCount(2);

	await recent.getByLabel('Provider').selectOption('oura');

	await expect(page).toHaveURL(`/users/${CONNECTED}?sync=oura`);
	await expect(recent.getByRole('listitem')).toHaveCount(1);
	await expect(recent.getByText('Processing')).toHaveCount(0);
});

test('keeps the external id out of the page but editable', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await expect(page.getByText('ext-0007')).toHaveCount(0);

	await page.getByRole('button', { name: 'Edit user' }).click();
	await expect(page.getByLabel('External user ID')).toHaveValue('ext-0007');
});

test('revokes a connection from its own menu', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await page.getByRole('button', { name: 'Actions for Garmin' }).click();
	await page.getByRole('button', { name: 'Revoke connection' }).click();
	await page.getByRole('button', { name: 'Revoke', exact: true }).click();

	await expect(page.getByRole('article').filter({ hasText: 'Garmin' })).toHaveCount(0);
	await expect(page.getByRole('article')).toHaveCount(2);
});

test('issues a mobile invitation code and shows what to type into the app', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await page.getByRole('button', { name: 'Mobile app' }).click();

	const dialog = page.getByRole('dialog', { name: 'Connect mobile app' });
	await expect(dialog.getByRole('textbox', { name: 'Invitation code' })).toHaveValue('ABCD-1234');
	// The address a phone dials, not the one the SvelteKit server uses.
	await expect(dialog.getByRole('textbox', { name: 'API URL' })).toHaveValue(
		'http://localhost:8787'
	);
});

test('keeps backfill history and live activity apart', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);

	// Backfills are the durable record: the covered window, not when it ran.
	const oura = page.getByRole('article').filter({ hasText: 'Oura' });
	await oura.getByText(/Historical backfill log/).click();
	await expect(oura.getByText('19 Jul 2025 – 19 Jul 2026')).toBeVisible();
	await expect(oura.getByText('Token expired while fetching daily_sleep')).toBeVisible();
	// A run that wrote nothing says so, rather than showing two zeroes.
	await expect(oura.getByText('Nothing saved')).toBeVisible();

	// Created and refreshed are reported apart: a backfill that only touched
	// rows it already had is a different outcome from one that found data.
	const garmin = page.getByRole('article').filter({ hasText: 'Garmin' });
	await garmin.getByText(/Historical backfill log/).click();
	await expect(garmin.getByText('8421 new')).toBeVisible();
	await expect(garmin.getByText('12 updated')).toBeVisible();

	// The 24h buffer is a separate section and carries the in-progress run, whose
	// source is a glyph but still has an accessible name.
	const recent = page.getByRole('region').filter({ hasText: 'Recent sync activity' });
	await expect(recent.getByText('Processing')).toBeVisible();
	await expect(recent.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60');
	await expect(recent.getByTitle('Webhook')).toBeVisible();

	// A run that reports its counts shows them; one that does not falls back to
	// the message, which is all the API gives today.
	await expect(recent.getByText('19058')).toBeVisible();
	await expect(recent.getByText('10223')).toBeVisible();
	await expect(recent.getByText('Writing heart rate samples')).toBeVisible();
});

test('offers the empty states rather than blank panels when nothing is connected', async ({
	page
}) => {
	await page.goto(`/users/${UNCONNECTED}`);

	await expect(page.getByText('No providers connected')).toBeVisible();
	await expect(page.getByText('Nothing in the last 24 hours')).toBeVisible();
});

test("gates Women's Health on the user actually having that data", async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await expect(page.getByRole('link', { name: "Women's Health" })).toBeVisible();

	await page.goto(`/users/${UNCONNECTED}`);
	await expect(page.getByRole('link', { name: "Women's Health" })).toHaveCount(0);
});

test('gives every tab a real URL, and 404s on one that is not a tab', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await page.getByRole('link', { name: 'Sleep' }).click();

	await expect(page).toHaveURL(`/users/${CONNECTED}/sleep`);
	await expect(page.getByText('Sleep is not built yet')).toBeVisible();

	const response = await page.goto(`/users/${CONNECTED}/not-a-tab`);
	expect(response?.status()).toBe(404);
});

test('edits the user from the profile and reflects it in the header', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await page.getByRole('button', { name: 'Edit user' }).click();

	await page.getByLabel('First name').fill('Zofia-Maria');
	await page.getByRole('button', { name: 'Save changes' }).click();

	await expect(page.getByRole('heading', { name: 'Zofia-Maria Kowalska' })).toBeVisible();
});

test('returns to the list after deleting, since the page it was on is gone', async ({ page }) => {
	await page.goto(`/users/${CONNECTED}`);
	await page.getByRole('button', { name: 'More user actions' }).click();
	await page.getByRole('button', { name: 'Delete user' }).click();
	await page
		.getByRole('dialog', { name: 'Delete user' })
		.getByRole('button', { name: 'Delete user' })
		.click();

	await expect(page).toHaveURL('/users');
	await expect(page.getByText('Zofia')).toHaveCount(0);
});
