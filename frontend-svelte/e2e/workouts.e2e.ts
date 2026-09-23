import { expect, test } from '@playwright/test';
import { signIn } from './support';

const USER = '00000000-0000-4000-8000-000000000007';
const WORKOUTS = `/users/${USER}/workouts`;

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('lists workouts newest first, with a dash where the provider sent nothing', async ({
	page
}) => {
	await page.goto(WORKOUTS);

	const cards = page.getByRole('article');
	await expect(cards).toHaveCount(10);
	await expect(cards.first().getByRole('heading')).toContainText('Running');

	// Strength training has no distance and Oura reports no workout heart rate.
	// A dash is the honest answer; a zero would be a measurement.
	const strength = cards.filter({ hasText: 'Strength training' }).first();
	await expect(strength.getByText('—')).toHaveCount(1);
	await expect(strength.getByText('240 kcal')).toBeVisible();

	// Same bar as the users list, minus the numbered links a cursor cannot offer.
	const pager = page.getByRole('navigation', { name: 'Pagination' });
	await expect(pager).toContainText('1–10 of 23');
	await expect(pager).toContainText('1 / 3');
	await expect(pager.getByRole('link', { name: 'Page 2' })).toHaveCount(0);
});

test('sums the whole period, not the page in front of you', async ({ page }) => {
	await page.goto(WORKOUTS);

	// Ten cards are on screen; the figures above cover all 23.
	const summary = page.locator('[aria-label="Workout totals"]');
	await expect(summary.getByText('23', { exact: true })).toBeVisible();
	await expect(summary.getByText('Total time')).toBeVisible();

	// And they follow the filters, like every other control on this page.
	await page.getByRole('link', { name: 'Oura', exact: true }).click();
	await expect(summary.getByText('4', { exact: true })).toBeVisible();
});

test('reads the clock the workout was recorded in, not the reader’s', async ({ page }) => {
	await page.goto(WORKOUTS);

	// Stored as 07:12Z with a +02:00 offset, so the watch said 09:12.
	await expect(page.getByRole('article').first()).toContainText('09:12');
});

test('narrows by provider and by type together', async ({ page }) => {
	await page.goto(WORKOUTS);

	await page.getByRole('link', { name: 'Oura', exact: true }).click();
	const cards = page.getByRole('article');
	await expect(cards.first().getByRole('heading')).toContainText('Swimming');
	await expect(cards.filter({ hasText: 'Running' })).toHaveCount(0);

	// Wait for the clearing navigation to land: the select builds its href from
	// the current URL, so firing it mid-flight would keep the provider.
	await page.getByRole('link', { name: 'All', exact: true }).click();
	await expect(page).toHaveURL(WORKOUTS);

	await page.getByLabel('Type').selectOption('cycling');

	await expect(page).toHaveURL(`${WORKOUTS}?type=cycling`);
	await expect(page.getByRole('article').first().getByRole('heading')).toContainText('Cycling');
});

test('pages through cursors, and a new filter starts from the first page', async ({ page }) => {
	await page.goto(WORKOUTS);
	const first = await page.getByRole('article').first().textContent();

	await page.getByRole('link', { name: 'Next page' }).click();
	await expect(page).toHaveURL(/cursor=/);
	await expect(page.getByRole('article').first()).not.toHaveText(first ?? '');
	await expect(page.getByRole('navigation', { name: 'Pagination' })).toContainText('2 / 3');

	// A cursor names a position in one query. Carried into a narrowed list it
	// would answer page one with page three of a list that no longer exists.
	await page.getByLabel('Type').selectOption('swimming');
	await expect(page).toHaveURL(`${WORKOUTS}?type=swimming`);
	await expect(page.getByRole('link', { name: 'Previous page' })).toHaveCount(0);
});

test('offers only the workout types this user actually has', async ({ page }) => {
	await page.goto(WORKOUTS);

	// From the timeline, so a sport nobody recorded is not in the list to pick.
	const options = page.getByLabel('Type').locator('option');
	await expect(options).toHaveText([
		'All types',
		'Cycling',
		'Open water swimming',
		'Running',
		'Strength training',
		'Swimming'
	]);
});

test('says so when the filters match nothing, rather than showing an empty list', async ({
	page
}) => {
	await page.goto(`${WORKOUTS}?provider=oura&type=running`);

	await expect(page.getByText('No workouts match these filters')).toBeVisible();
	await expect(page.getByRole('article')).toHaveCount(0);
});

test('drops filter values this user has no data for rather than failing', async ({ page }) => {
	// Both are backend enums, so forwarding an invented one would 422 the load.
	await page.goto(`${WORKOUTS}?provider=nonsense&type=quidditch`);

	await expect(page.getByRole('article').first()).toBeVisible();
	await expect(page.getByRole('link', { name: 'All', exact: true })).toHaveAttribute(
		'aria-current',
		'true'
	);
});

test('opens on the statistics too, not only on the header', async ({ page }) => {
	await page.goto(WORKOUTS);
	const card = page.getByRole('article').first();

	await card.getByText('Duration').click();
	await expect(card.getByRole('button').first()).toHaveAttribute('aria-expanded', 'true');

	await card.getByText('Duration').click();
	await expect(card.getByRole('button').first()).toHaveAttribute('aria-expanded', 'false');
});

test('opens one workout for the rest of what the provider sent', async ({ page }) => {
	await page.goto(WORKOUTS);
	const card = page.getByRole('article').first();

	const toggle = card.getByRole('button').first();
	await expect(toggle).toHaveAttribute('aria-expanded', 'false');
	await toggle.click();

	// Fields the collapsed row has no room for, and only the ones that exist:
	// a dozen dashes here would say nothing.
	await expect(card.getByText('176 bpm')).toBeVisible();
	await expect(card.getByText('Cadence')).toBeVisible();
	await expect(card.getByText('9,400')).toBeVisible();

	// Garmin reports zones from a FIT file; the bar is drawn from seconds per zone.
	await expect(card.getByText('Time in heart rate zones')).toBeVisible();

	// One kind at a time, and the run has only the one, so there is nothing to
	// switch between.
	await expect(card.getByRole('group', { name: 'Zones' })).toHaveCount(0);

	await toggle.click();
	await expect(card.getByText('Cadence')).toHaveCount(0);
});

test('draws the readings inside the workout, and only once it is opened', async ({ page }) => {
	const calls: string[] = [];
	page.on('request', (request) => {
		if (request.url().includes('/workouts/samples')) calls.push(request.url());
	});

	await page.goto(WORKOUTS);
	// Ten cards on screen, none of them asking for a curve.
	expect(calls).toEqual([]);

	const card = page.getByRole('article').first();
	await card.getByRole('button').first().click();

	const chart = card.getByRole('img', { name: 'Sensor readings across the workout' });
	await expect(chart).toBeVisible();
	expect(calls).toHaveLength(1);

	// Two devices recorded this run. The API returns a row per bucket *per source*,
	// so merging them by timestamp would saw between two watches instead of
	// drawing either curve: each device gets its own named line.
	await expect(card.getByRole('button', { name: 'Heart rate · Forerunner 265' })).toBeVisible();
	await expect(card.getByRole('button', { name: 'Heart rate · Apple Watch' })).toBeVisible();
	await expect(card.getByRole('button', { name: 'Power' })).toHaveCount(0);

	// Hovering reports the reading under the pointer, which is the whole point of
	// a curve an admin is reading rather than admiring.
	await chart.hover();
	await expect(card.locator('.pointer-events-none').filter({ hasText: 'bpm' })).toBeVisible();
});

test('deletes a workout after confirming, and the list agrees afterwards', async ({ page }) => {
	await page.goto(WORKOUTS);
	const pager = page.getByRole('navigation', { name: 'Pagination' });
	await expect(pager).toContainText('of 23');

	await page.getByRole('article').first().getByRole('button').first().click();
	await page.getByRole('button', { name: 'Delete workout' }).click();
	await page.getByRole('button', { name: 'Delete', exact: true }).click();

	// The count comes from the API, so a stale one would mean the page never
	// reloaded — which is the whole risk with an enhanced form.
	await expect(pager).toContainText('of 22');
	await expect(page.getByRole('article').first().getByRole('heading')).toContainText('Cycling');
});

test('walks the whole list forward and back again', async ({ page }) => {
	await page.goto(WORKOUTS);
	const pager = page.getByRole('navigation', { name: 'Pagination' });
	const heading = () => page.getByRole('article').first().getByRole('heading').textContent();

	const forward: (string | null)[] = [await heading()];
	for (const position of ['2 / 3', '3 / 3']) {
		await pager.getByRole('link', { name: 'Next page' }).click();
		await expect(pager).toContainText(position);
		forward.push(await heading());
	}

	// The last page has nowhere further to go, and says so rather than looping.
	await expect(pager.getByRole('link', { name: 'Next page' })).toHaveCount(0);
	await expect(pager).toContainText('21–23 of 23');

	// Back one page at a time, not all the way to the start: a `prev_` cursor
	// names the page before, not the beginning.
	for (const position of ['2 / 3', '1 / 3']) {
		await pager.getByRole('link', { name: 'Previous page' }).click();
		await expect(pager).toContainText(position);
	}

	expect(await heading()).toBe(forward[0]);
	expect(new Set(forward).size).toBe(3);

	// Page one has nothing before it, so reached by a prev_ cursor the API reports
	// has_more false and withholds the forward cursor with it. Landing on the bare
	// URL instead is what keeps the way out alive.
	await expect(page).toHaveURL(WORKOUTS);
	await pager.getByRole('link', { name: 'Next page' }).click();
	await expect(pager).toContainText('2 / 3');
});

test('switches which zones the strip and the chart bands show', async ({ page }) => {
	await page.goto(WORKOUTS);
	// The bike carries both kinds; the run carries only heart rate.
	const card = page.getByRole('article').nth(1);
	await card.getByText('Duration').click();

	const chart = card.getByRole('img', { name: 'Sensor readings across the workout' });
	await expect(chart).toBeVisible();
	await expect(card.getByText('Time in heart rate zones')).toBeVisible();
	await expect(card.getByText('Bands: heart rate zones')).toBeVisible();

	// Bands and strip answer to one control, so the chart can never be shading
	// one kind while the rows below count the other.
	await card.getByRole('group', { name: 'Zones' }).getByText('Power').click();

	await expect(card.getByText('Time in power zones')).toBeVisible();
	await expect(card.getByText('Bands: power zones')).toBeVisible();
	await expect(card.getByText('Time in heart rate zones')).toHaveCount(0);
});

test('shows the cards without waiting for the figures above them', async ({ page, request }) => {
	// Summing the period reads every record in it, and there is no aggregate
	// endpoint to ask instead — so it is its own request and the list must not
	// queue behind it.
	await request.post('http://localhost:8787/__slow/workouts-summary');
	await page.goto(WORKOUTS);

	const figures = page.locator('[aria-label="Workout totals"]');
	await expect(page.getByRole('article').first()).toBeVisible();
	await expect(figures).toHaveCount(0);

	await expect(figures.getByText('23', { exact: true })).toBeVisible();
});

test('says which day a workout ended on when it runs past midnight', async ({ page }) => {
	await page.goto(`${WORKOUTS}?type=open_water_swimming`);

	// Dated by its start, so the weekday belongs to the *end*: marking the start
	// repeats the date beside it and leaves the finish looking like it happened
	// earlier the same day.
	const heading = page.getByRole('article').first().getByRole('heading');
	await expect(heading).toContainText('22:30');
	await expect(heading).toContainText(/\w{3}\s*02:19/);
});
