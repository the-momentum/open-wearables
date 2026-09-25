import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const UNCONNECTED = '00000000-0000-4000-8000-000000000003';
const SCORES = `/users/${USER}/scores`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('opens on a tile per category, each with its own range', async ({ page }) => {
	await page.goto(SCORES);

	// Sleep is scored by Oura and by Open Wearables, so its tile carries two
	// lines, names both, and shows the one range they are drawn against. OW's own
	// scores are stored under the `internal` provider, which is not an OAuth
	// connection and so is named here rather than by the provider catalogue.
	const sleep = page.getByRole('link', { name: /^Sleep \d/ });
	await expect(sleep).toContainText('OW');
	await expect(sleep).toContainText('Oura');
	await expect(sleep).toContainText(/\d+–\d+/);

	await expect(page.getByRole('link', { name: /^Readiness \d/ })).toBeVisible();
	await expect(page.getByRole('link', { name: /^Recovery \d/ })).toBeVisible();
});

test('reads resilience off its component, not off the raw variability', async ({ page }) => {
	await page.goto(`${SCORES}?category=resilience`);

	// `value` on these rows is an HRV coefficient of variation around 0.1. The
	// score is the 0-100 number beside it, and the fraction appears only under
	// its own name.
	const card = page.getByRole('article').first();
	await expect(card.getByText(/^\d\d$/)).toBeVisible();
	await expect(card.getByText(/^0\.\d+$/)).toHaveCount(0);

	await card.getByRole('button').first().click();
	await expect(card.getByText('HRV variability')).toBeVisible();
	await expect(card.getByText(/^\d+\.\d%$/)).toBeVisible();
});

test('puts both providers for a night on one card', async ({ page }) => {
	await page.goto(`${SCORES}?category=sleep`);

	// Not getByText: the provider mark wears the same two letters as the label.
	const card = page.getByRole('article').first();
	await expect(card).toContainText('Oura');
	await expect(card).toContainText('OW');

	// Opening it gives each provider its own column of components, because what
	// the two scores were made of is the reason to compare them.
	await card.getByRole('button').first().click();
	await expect(card.getByText('Restfulness')).toBeVisible();
	await expect(card.getByText('Interruptions')).toBeVisible();
});

test('collapses a provider that scores all day into one card and a curve', async ({ page }) => {
	await page.goto(`${SCORES}?category=recovery`);

	// Suunto's stress-recovery stream arrives many times a day. One card a day
	// with the mean, and the span the mean hides beside it.
	const card = page.getByRole('article').first();
	await expect(card.getByText(/\d+–\d+ over \d+ readings/)).toBeVisible();

	// Opened, the day's own curve — drawn from readings the page already has, so
	// it costs no request.
	await card.getByRole('button').first().click();
	await expect(card.getByLabel('Recovery readings across the day')).toBeVisible();
});

test('pages in days, because a card is a day', async ({ page }) => {
	await page.goto(SCORES);

	// The endpoint pages by record, and a page of twenty records is two cards for
	// a provider that scores every half hour. So a page is ten days of the
	// ninety-day window instead.
	const bar = page.getByRole('navigation', { name: 'Pagination' });
	await expect(bar).toContainText('1–10 of 110 days');
	await expect(page.getByRole('article')).toHaveCount(10);

	await bar.getByRole('link', { name: 'Page 11' }).click();
	await expect(page).toHaveURL(/page=11/);
	await expect(bar).toContainText('101–110 of 110 days');
	await expect(page.getByRole('article')).toHaveCount(10);
});

test('pages the whole history under All time, rather than snapping to a preset', async ({
	page
}) => {
	await page.goto(SCORES);

	// Paging by day needs a first day to count back from, and this endpoint only
	// answers newest-first — so All time finds its own start from the oldest
	// score rather than being quietly replaced by the ninety-day range.
	const period = page.getByRole('group', { name: 'Period' });
	await expect(period.getByRole('link', { name: 'All time' })).toHaveAttribute(
		'aria-current',
		'true'
	);
	await expect(page.getByRole('navigation', { name: 'Pagination' })).toContainText('of 110 days');

	// The preset is ninety, so the two are told apart by the count.
	await period.getByRole('link', { name: 'Range' }).click();
	await expect(page.getByRole('navigation', { name: 'Pagination' })).toContainText('of 90 days');
});

test('says how far back the trends actually reach when the period will not fit', async ({
	page
}) => {
	await page.goto(SCORES);

	// Ninety days of a half-hourly stream is more than one page of records, so
	// the trends cover the most recent stretch and name it.
	await expect(page.getByText(/^Trends: /)).toBeVisible();
});

test('narrows to one category and draws it full size', async ({ page }) => {
	await page.goto(SCORES);

	// The tiles are the chooser: picking one is what narrows the list below.
	await page.getByRole('link', { name: /^Readiness \d/ }).click();

	await expect(page).toHaveURL(/category=readiness/);
	await expect(page.getByLabel('Readiness score over the period')).toBeVisible();
	await expect(page.getByText(/^\d+ days$/)).toBeVisible();

	// One chart in place of the tiles, and every card is that category now.
	await expect(page.getByRole('link', { name: /^Sleep \d/ })).toHaveCount(0);
	await expect(page.getByRole('article').first()).toContainText('Readiness');
});

test('keeps the category when the period changes, and returns to page one', async ({ page }) => {
	await page.goto(`${SCORES}?category=sleep&page=3`);

	await page.getByRole('group', { name: 'Period' }).getByRole('link', { name: 'Range' }).click();

	await expect(page).toHaveURL(/category=sleep/);
	await expect(page).not.toHaveURL(/page=3/);
});

test('says so when the user has no scores at all', async ({ page }) => {
	await page.goto(`/users/${UNCONNECTED}/scores`);

	await expect(page.getByText('No scores recorded')).toBeVisible();
	await expect(page.getByText('No score was recorded in this period')).toBeVisible();
});
