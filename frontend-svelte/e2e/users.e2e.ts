import { expect, test } from '@playwright/test';
import { pager, signIn } from './support';

const MOBILE = { width: 390, height: 844 };

// The write tests mutate the stand-in backend, so each test starts from a
// known set rather than inheriting the previous one's edits.
test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
	await page.goto('/users');
});

test('lists the first page and reports the total', async ({ page }) => {
	await expect(page.getByRole('table')).toBeVisible();
	await expect(page.getByRole('row')).toHaveCount(21); // 20 users plus the header
	await expect(pager(page).getByText('1–20 of 47')).toBeVisible();
});

test('shows a truncated id that copies in full', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);

	const row = page.getByRole('row').nth(1);
	await expect(row.getByText('0000…')).toBeVisible();

	await row.getByRole('button', { name: 'Copy user ID' }).click();

	await expect(row.getByRole('button', { name: 'user ID copied' })).toBeVisible();
	// The full id must land on the clipboard, not the truncated label.
	expect(await page.evaluate(() => navigator.clipboard.readText())).toMatch(
		/^[0-9a-f]{8}-[0-9a-f]{4}-/
	);
});

test('changes the page size and keeps the first visible row visible', async ({ page }) => {
	// Page 2 at 20 per page shows rows 21-40.
	await page.goto('/users?page=2');
	await expect(pager(page).getByText('21–40 of 47')).toBeVisible();

	await pager(page).getByLabel('Per page').selectOption('50');

	// Row 21 must still be on screen, so page 1 of 50 (rows 1-50).
	await expect(page).toHaveURL('/users?size=50');
	await expect(pager(page).getByText('1–47 of 47')).toBeVisible();
});

test('rescues a page number past the end of the data', async ({ page }) => {
	await page.goto('/users?page=99');

	await expect(page).toHaveURL('/users?page=3');
	await expect(pager(page).getByText('41–47 of 47')).toBeVisible();
});

test('keeps the page size when the search changes', async ({ page }) => {
	await page.goto('/users?size=100');
	await expect(pager(page).getByText('1–47 of 47')).toBeVisible();

	await page.getByRole('searchbox', { name: 'Search users' }).fill('Kowalska');
	await expect(page).toHaveURL('/users?size=100&search=Kowalska');
});

// Two bars, so the size can be changed without scrolling a full page of rows.
test('carries a working pagination bar above and below the list', async ({ page }) => {
	for (const label of ['Pagination above the list', 'Pagination below the list']) {
		const bar = page.getByRole('navigation', { name: label });
		await expect(bar.getByText('1–20 of 47')).toBeVisible();
		await expect(bar.getByRole('link', { name: 'Page 2' })).toBeVisible();
		await expect(bar.getByLabel('Per page')).toBeVisible();
	}

	await page
		.getByRole('navigation', { name: 'Pagination above the list' })
		.getByRole('link', { name: 'Next page' })
		.click();

	await expect(page).toHaveURL('/users?page=2');
});

test('creates a user and shows them in the list', async ({ page }) => {
	await page.getByRole('button', { name: 'Add user' }).click();

	const dialog = page.getByRole('dialog', { name: 'Add user' });
	await dialog.getByLabel('First name').fill('Nowa');
	await dialog.getByLabel('Last name').fill('Osoba');
	await dialog.getByLabel('Email').fill('nowa@example.com');
	await dialog.getByRole('button', { name: 'Create user' }).click();

	await expect(dialog).toBeHidden();
	await expect(page.getByRole('table').getByText('nowa@example.com')).toBeVisible();
});

// The backend answers 409; the message must be readable, not the raw detail.
test('keeps the form open and explains a duplicate email', async ({ page }) => {
	await page.getByRole('button', { name: 'Add user' }).click();

	const dialog = page.getByRole('dialog', { name: 'Add user' });
	await dialog.getByLabel('Email').fill('zofia@example.com');
	await dialog.getByRole('button', { name: 'Create user' }).click();

	await expect(dialog.getByRole('alert')).toContainText('already exists');
	await expect(dialog).toBeVisible();
});

test('edits a user from the row', async ({ page }) => {
	await page.goto('/users?search=Kowalska');
	await page.getByRole('row').nth(1).getByRole('button', { name: /^Edit/ }).click();

	const dialog = page.getByRole('dialog', { name: 'Edit user' });
	await expect(dialog.getByLabel('First name')).toHaveValue('Zofia');

	await dialog.getByLabel('First name').fill('Zofia Maria');
	await dialog.getByRole('button', { name: 'Save changes' }).click();

	await expect(dialog).toBeHidden();
	await expect(page.getByRole('table').getByText('Zofia Maria Kowalska')).toBeVisible();
});

// enhance resets the form on success, which clears the DOM values; reopening
// must repopulate rather than show a blank form.
test('reopens the edit form still populated after a save', async ({ page }) => {
	await page.goto('/users?search=Kowalska');
	const row = page.getByRole('row').nth(1);

	await row.getByRole('button', { name: /^Edit/ }).click();
	const dialog = page.getByRole('dialog', { name: 'Edit user' });
	await dialog.getByRole('button', { name: 'Save changes' }).click();
	await expect(dialog).toBeHidden();

	await row.getByRole('button', { name: /^Edit/ }).click();

	await expect(dialog.getByLabel('First name')).toHaveValue('Zofia');
	await expect(dialog.getByLabel('Last name')).toHaveValue('Kowalska');
	await expect(dialog.getByLabel('Email')).toHaveValue('zofia@example.com');
});

test('deletes a user after confirming', async ({ page }) => {
	await page.goto('/users?search=Kowalska');
	await expect(pager(page).getByText('1–1 of 1')).toBeVisible();

	await page
		.getByRole('row')
		.nth(1)
		.getByRole('button', { name: /^Delete/ })
		.click();

	const dialog = page.getByRole('dialog', { name: 'Delete user' });
	await expect(dialog).toContainText('Zofia Kowalska');
	await dialog.getByRole('button', { name: 'Delete user' }).click();

	await expect(dialog).toBeHidden();
	await expect(page.getByText('No users match')).toBeVisible();
});

test('copies a pairing link pointing at this app', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);

	const row = page.getByRole('row').nth(1);
	await row.getByRole('button', { name: /^Copy pairing link/ }).click();

	await expect(row.getByRole('button', { name: 'Pairing link copied' })).toBeVisible();
	expect(await page.evaluate(() => navigator.clipboard.readText())).toMatch(
		/^http:\/\/localhost:4173\/users\/[0-9a-f-]{36}\/pair$/
	);
});

test('opens a user from anywhere in the row', async ({ page }) => {
	// force: the overlay link covers the cell, which is the thing being tested —
	// without it Playwright refuses to click "through" another element.
	await page.getByRole('row').nth(1).getByRole('cell').nth(3).click({ force: true });

	await expect(page).toHaveURL(/\/users\/[0-9a-f-]{36}$/);
});

test('copying the id does not open the user', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);

	await page.getByRole('row').nth(1).getByRole('button', { name: 'Copy user ID' }).click();

	await expect(page).toHaveURL('/users');
});

test('filters by provider, with the list coming from the backend', async ({ page }) => {
	const trigger = page.getByRole('button', { name: /^Provider/ });

	// Wrapping this in the shared Button once dropped both attributes silently.
	await expect(trigger).toHaveAttribute('aria-haspopup', 'dialog');
	await expect(trigger).toHaveAttribute('aria-expanded', 'false');

	await trigger.click();
	await expect(trigger).toHaveAttribute('aria-expanded', 'true');

	const panel = page.getByRole('dialog', { name: 'Filter by provider' });
	await panel.getByRole('button', { name: 'Garmin' }).click();
	await panel.getByRole('button', { name: 'Apply' }).click();

	await expect(page).toHaveURL('/users?provider=garmin');
	await expect(
		page
			.getByRole('table')
			.getByTitle(/garmin/)
			.first()
	).toBeVisible();
});

// Selecting used to navigate per chip, which closed the panel each time.
test('picks several providers in one visit and one navigation', async ({ page }) => {
	await page.getByRole('button', { name: /^Provider/ }).click();

	const panel = page.getByRole('dialog', { name: 'Filter by provider' });
	await panel.getByRole('button', { name: 'Garmin' }).click();
	await expect(panel).toBeVisible();
	await panel.getByRole('button', { name: 'Oura' }).click();
	await expect(panel).toBeVisible();

	await expect(page).toHaveURL('/users');

	await panel.getByRole('button', { name: 'Apply' }).click();
	await expect(page).toHaveURL('/users?provider=garmin&provider=oura');
	await expect(page.getByRole('button', { name: /^Provider/ })).toContainText('2');
});

test('removes one selected provider from the summary, or clears them all', async ({ page }) => {
	await page.goto('/users?provider=garmin&provider=oura');

	await page.getByRole('link', { name: 'Garmin', exact: true }).click();
	await expect(page).toHaveURL('/users?provider=oura');

	await page.getByRole('link', { name: 'Clear' }).click();
	await expect(page).toHaveURL('/users');
	await expect(pager(page).getByText('1–20 of 47')).toBeVisible();
});

test('shows connection badges from the include=connections expansion', async ({ page }) => {
	await expect(page.getByRole('listitem').filter({ hasText: 'garmin' }).first()).toBeVisible();
	await expect(page.getByText('No connections').first()).toBeVisible();
});

test('pages forward and back, keeping the position in the URL', async ({ page }) => {
	await pager(page).getByRole('link', { name: 'Next page' }).click();

	await expect(page).toHaveURL('/users?page=2');
	await expect(pager(page).getByText('21–40 of 47')).toBeVisible();

	await page.goBack();
	await expect(page).toHaveURL('/users');
	await expect(pager(page).getByText('1–20 of 47')).toBeVisible();
});

test('searches without stacking a history entry per keystroke', async ({ page }) => {
	// Slower than the 300ms debounce on purpose, so each character really does
	// navigate. With pushState this would leave three entries behind.
	await page
		.getByRole('searchbox', { name: 'Search users' })
		.pressSequentially('Kow', { delay: 400 });

	await expect(page).toHaveURL('/users?search=Kow');

	await page.goBack();
	await expect(page).toHaveURL('/dashboard');
});

test('finds a user by pasting their id, which the API matches exactly', async ({ page }) => {
	await page
		.getByRole('searchbox', { name: 'Search users' })
		.fill('00000000-0000-4000-8000-000000000007');

	await expect(pager(page).getByText('1–1 of 1')).toBeVisible();
	// Scoped to the table: the mobile cards render the same names, hidden by CSS.
	await expect(page.getByRole('table').getByText('Zofia Kowalska')).toBeVisible();
});

test('sorts by a column and says so for assistive tech', async ({ page }) => {
	await page.getByRole('columnheader', { name: 'User' }).getByRole('link').click();

	await expect(page).toHaveURL('/users?sort=name');
	await expect(page.getByRole('columnheader', { name: 'User' })).toHaveAttribute(
		'aria-sort',
		'descending'
	);
});

test('returns to the first page when the search changes', async ({ page }) => {
	await pager(page).getByRole('link', { name: 'Next page' }).click();
	await expect(page).toHaveURL('/users?page=2');

	await page.getByRole('searchbox', { name: 'Search users' }).fill('Kowalska');
	await expect(page).toHaveURL('/users?search=Kowalska');
});

test('reports an empty search rather than showing a blank table', async ({ page }) => {
	await page.getByRole('searchbox', { name: 'Search users' }).fill('nobodyhere');

	await expect(page.getByText('No users match')).toBeVisible();
	await expect(page.getByRole('table')).toBeHidden();
});

test.describe('mobile', () => {
	test.use({ viewport: MOBILE });

	test('shows cards instead of a table', async ({ page }) => {
		await expect(page.getByRole('table')).toBeHidden();
		await expect(page.getByRole('article').first()).toBeVisible();
		await expect(pager(page).getByText('1–20 of 47')).toBeVisible();
	});

	test('keeps the page counter compact instead of numbered links', async ({ page }) => {
		await expect(pager(page).getByText('1 / 3')).toBeVisible();
		await expect(pager(page).getByRole('link', { name: 'Page 3' })).toBeHidden();
	});
});
