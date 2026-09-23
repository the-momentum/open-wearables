import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { signIn } from './support';

const sent = async (request: APIRequestContext) =>
	(await (await request.get('http://localhost:8787/__last-seed')).json()).request;

/** The accordion headers, not the presets that share their words. */
const section = (page: Page, name: string) =>
	page.locator('[data-accordion-toggle]').filter({ hasText: name });

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
	await page.goto('/settings/seed-data');
});

test('opens on the quickest preset and reads the request back in one sentence', async ({
	page
}) => {
	await expect(page.getByRole('button', { name: /^Minimal \(Quick\)/ })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(
		page.getByText(
			'1 user, 2 random connections each, each with 5 workouts, 5 nights, over the last 6 months.'
		)
	).toBeVisible();
});

test('follows a preset, lets go on an edit and picks it up again when undone', async ({ page }) => {
	const athlete = page.getByRole('button', { name: /^Active Athlete/ });
	await athlete.click();
	await expect(athlete).toHaveAttribute('aria-pressed', 'true');
	await expect(section(page, 'Workouts')).toContainText('120 workouts');

	await section(page, 'Workouts').click();
	const count = page.getByLabel('Per user', { exact: true }).first();
	await count.fill('121');
	// Derived, not remembered: the preset is simply no longer what the form says.
	await expect(athlete).toHaveAttribute('aria-pressed', 'false');
	await expect(page.getByText('Custom', { exact: true }).first()).toBeVisible();

	await count.fill('120');
	await expect(athlete).toHaveAttribute('aria-pressed', 'true');
});

test('sends the preset as it is, and says where to find the result', async ({ page, request }) => {
	await page.getByRole('button', { name: 'Generate', exact: true }).click();

	await expect(page.getByText('Queued one user.')).toBeVisible();
	await expect(page.getByText('424242')).toBeVisible();
	await expect(page.getByRole('link', { name: /appear in Users/ })).toHaveAttribute(
		'href',
		'/users'
	);

	const body = await sent(request);
	expect(body.num_users).toBe(1);
	expect(body.random_seed).toBeNull();
	expect(body.profile).toMatchObject({ preset: 'minimal', providers: null, num_connections: 2 });
});

test('lets the picked providers set the connection count', async ({ page, request }) => {
	for (const name of ['Garmin', 'Oura', 'Whoop']) {
		await page.getByRole('button', { name, exact: true }).click();
	}
	await expect(page.getByText('Each user connects to all 3.')).toBeVisible();
	await page.getByRole('button', { name: 'Generate', exact: true }).click();
	await expect(page.getByText('Queued one user.')).toBeVisible();

	// The backend keeps providers[:num_connections]: a count left at 2 would
	// quietly have dropped Whoop.
	expect((await sent(request)).profile).toMatchObject({
		providers: ['garmin', 'oura', 'whoop'],
		num_connections: 3
	});
});

test('applies one window to all three kinds of data', async ({ page, request }) => {
	await page.getByRole('button', { name: 'Dates' }).click();
	await page.getByLabel('From', { exact: true }).fill('2026-01-01');
	await page.getByLabel('To', { exact: true }).fill('2026-03-31');
	await page.getByRole('button', { name: 'Generate', exact: true }).click();
	await expect(page.getByText('Queued one user.')).toBeVisible();

	const { profile } = await sent(request);
	for (const config of [profile.workout_config, profile.sleep_config, profile.time_series_config]) {
		expect(config).toMatchObject({ date_from: '2026-01-01', date_to: '2026-03-31' });
	}
});

test('passes a chosen seed through, so a run can be made again', async ({ page, request }) => {
	await page.getByLabel('Seed').fill('1234');
	await page.getByRole('button', { name: 'Generate', exact: true }).click();

	await expect(page.getByText('1234', { exact: true })).toBeVisible();
	expect((await sent(request)).random_seed).toBe(1234);
});

test('will not send what the API would refuse, and says why', async ({ page }) => {
	await page.getByLabel('Users').fill('11');

	await expect(page.getByText('Users must be 1 to 10.')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Generate', exact: true })).toBeDisabled();
});

test('keeps each section folded to one line until it is opened', async ({ page }) => {
	await expect(section(page, 'Sleep')).toContainText('5 nights');
	await expect(page.getByRole('group', { name: 'Length' })).toHaveCount(0);

	await section(page, 'Sleep').click();
	await expect(page.getByRole('group', { name: 'Length' })).toBeVisible();
});

test('offers only the series the generator can make, the workout-bound ones apart', async ({
	page
}) => {
	await page.getByRole('button', { name: /^Active Athlete/ }).click();
	await section(page, 'Time series').click();

	await expect(page.getByText('During workouts', { exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Running power', exact: true })).toBeVisible();
});

test('fits a phone', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.reload();
	await section(page, 'Workouts').click();

	const width = await page.evaluate(() => document.documentElement.scrollWidth);
	expect(width).toBeLessThanOrEqual(390);
});
