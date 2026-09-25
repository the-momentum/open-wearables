import { expect, test } from '@playwright/test';
import { signIn } from './support';

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('compacts the aggregates and spells out the cheap counts', async ({ page }) => {
	await page.goto('/dashboard');

	// Users and connections are exact counts of small tables, so they are shown
	// whole. Data points and event records are aggregates — one of them an
	// estimate — so seven digits would claim a precision they have not got.
	await expect(page.getByText('1,247', { exact: true })).toBeVisible();
	await expect(page.getByText('1.5M', { exact: true })).toBeVisible();
	await expect(page.getByText('20.4K', { exact: true })).toBeVisible();
	await expect(page.getByText('estimated', { exact: true })).toBeVisible();
});

test('keeps every sub-metric on the tile, zero included', async ({ page }) => {
	await page.goto('/dashboard');

	// Each tile carries its own breakdown, and the archive figure is the one that
	// went missing when an empty part was simply left out. Scoped to the tiles:
	// the same counts appear again in the rankings below.
	const tiles = page.getByRole('region', { name: 'Platform totals' });
	await expect(tiles.getByText('archived', { exact: true })).toBeVisible();
	await expect(tiles.getByText('318K', { exact: true })).toBeVisible();
	await expect(tiles.getByText('cycles', { exact: true })).toBeVisible();
	await expect(tiles.getByText('220', { exact: true })).toBeVisible();
	await expect(tiles.getByText('users with two or more', { exact: true })).toBeVisible();
});

test('shows an empty archive as zero rather than hiding it', async ({ page, request }) => {
	await request.post('http://localhost:8787/__empty-archive');
	await page.goto('/dashboard');

	const tiles = page.getByRole('region', { name: 'Platform totals' });
	await expect(tiles.getByText('archived', { exact: true })).toBeVisible();
	await expect(tiles.getByText('0', { exact: true })).toBeVisible();
});

test('splits the user base into connected and not', async ({ page }) => {
	await page.goto('/dashboard');

	const connections = page.getByRole('region', { name: 'Connections' });
	// 902 of 1247.
	await expect(connections.getByText('72%')).toBeVisible();
	await expect(connections.getByText('No connection')).toBeVisible();
	await expect(connections.getByText('345 · 28%')).toBeVisible();
});

test('ranks the providers by name, with their counts grouped', async ({ page }) => {
	await page.goto('/dashboard');

	// `exact`, because getByText matches a substring and ignores case by default
	// — which is how an assertion on "WHOOP" passed against a rendered "Whoop".
	const connections = page.getByRole('region', { name: 'Connections' });
	await expect(connections.getByText('Garmin', { exact: true })).toBeVisible();
	await expect(connections.getByText('Whoop', { exact: true })).toBeVisible();
	// A count alone does not say whether that is half the estate or a tenth.
	await expect(connections.getByText('480 · 53%', { exact: true })).toBeVisible();
});

test('breaks the event records down by category', async ({ page }) => {
	await page.goto('/dashboard');

	const stored = page.getByRole('region', { name: 'Event records' });
	await expect(stored.getByText('Cycles', { exact: true })).toBeVisible();
	// Grouped, because a bare 11766 is a number nobody reads at a glance.
	await expect(stored.getByText('11,766', { exact: true })).toBeVisible();
});

test('lists the newest users with how long ago each one synced', async ({ page }) => {
	await page.goto('/dashboard');

	// Ten, and the limit is a readability choice: measured on 200k users, a page
	// of 100 costs the same as a page of 6 — the scan and the sort are paid
	// whatever it is.
	const newest = page.getByRole('region', { name: 'Newest users' });
	await expect(newest.getByRole('link')).toHaveCount(10);

	// Free: the list projection computes the last sync for the rows on this page.
	// Sorting every user by it is the query this dashboard refuses to make.
	await expect(newest.getByText('via', { exact: false }).first()).toBeVisible();
	await expect(newest.getByText('Never').first()).toBeVisible();

	// And the providers each one is connected to, which is what the list is for.
	await expect(newest.getByTitle(/^suunto: active$/).first()).toBeVisible();
	await expect(newest.getByText('No connections').first()).toBeVisible();

	await newest.getByRole('link').first().click();
	await expect(page).toHaveURL(/\/users\/[0-9a-f-]+$/);
});
