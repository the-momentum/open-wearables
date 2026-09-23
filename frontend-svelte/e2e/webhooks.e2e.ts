import { expect, test } from '@playwright/test';
import { signIn } from './support';

test.beforeEach(async ({ page, request }) => {
	await request.post('http://localhost:8787/__reset');
	await signIn(page);
});

test('calls them subscriptions, because that is what you are creating', async ({ page }) => {
	await page.goto('/webhooks');

	await expect(page.getByRole('heading', { name: 'Webhook subscriptions' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'New subscription' })).toBeVisible();
	await expect(page.getByText('Production listener')).toBeVisible();
});

test('opens a row from anywhere on it, not only the heading', async ({ page }) => {
	await page.goto('/webhooks');

	const card = page.getByRole('article').first();
	const toggle = card.getByRole('button', { name: /Production listener/ });
	await expect(toggle).toHaveAttribute('aria-expanded', 'false');

	// The padding and the gaps are card too: a click that lands there and does
	// nothing reads as a broken control.
	await card.click({ position: { x: 5, y: 5 } });
	await expect(toggle).toHaveAttribute('aria-expanded', 'true');
	await expect(card.getByText('Recent deliveries')).toBeVisible();
});

test('leaves the card alone when a control on it is clicked', async ({ page }) => {
	await page.goto('/webhooks');

	const card = page.getByRole('article').first();
	const toggle = card.getByRole('button', { name: /Production listener/ });

	// The card opens on a click anywhere, so its own buttons have to be the
	// exception — an edit that folded the row underneath the dialog would be one.
	await card.getByRole('button', { name: 'Edit' }).click();
	await expect(page.getByRole('dialog')).toContainText('Edit subscription');
	await expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

test('says when the webhook service returned no payload, rather than showing {}', async ({
	page
}) => {
	await page.goto('/webhooks/ep_live/deliveries');

	// Svix 2.x keeps both behind a `with_content` flag the backend does not set,
	// so an empty payload is "nobody asked", not "nothing was sent".
	const second = page.getByRole('button', { name: /series\.heart_rate/ }).first();
	await second.click();
	await expect(page.getByText('Not returned by the webhook service.').first()).toBeVisible();

	// The one delivery that does carry content still shows it.
	await page
		.getByRole('button', { name: /workout.created/ })
		.first()
		.click();
	await expect(page.getByText('"workout.created"').first()).toBeVisible();
});

test('filters deliveries by status and by event', async ({ page }) => {
	await page.goto('/webhooks/ep_live/deliveries');
	const rows = page.getByRole('button', { name: /created|heart_rate/ });
	await expect(rows).toHaveCount(20);

	await page.getByLabel('Status').selectOption('2');
	await expect(page).toHaveURL(/status=2/);
	await expect(page.getByRole('button', { name: /created|heart_rate/ })).toHaveCount(9);

	await page.getByLabel('Status').selectOption('');
	await page.getByLabel('Event').selectOption('workout.created');
	await expect(page).toHaveURL(/type=workout.created/);
	await expect(page.getByRole('button', { name: /heart_rate/ })).toHaveCount(0);
});

test('folds the event types into families instead of one wall of names', async ({ page }) => {
	await page.goto('/webhooks');
	await page.getByRole('button', { name: 'New subscription' }).click();

	// Closed by default, and a closed family still says how many it holds.
	const family = page.getByRole('button', { name: /^Heart rate/ });
	await expect(family).toHaveAttribute('aria-expanded', 'false');
	await expect(page.getByRole('button', { name: 'series.heart_rate', exact: true })).toHaveCount(0);

	await family.click();
	await expect(page.getByRole('button', { name: 'series.heart_rate', exact: true })).toBeVisible();
});

test('creates a subscription from the dialog', async ({ page }) => {
	await page.goto('/webhooks');
	await page.getByRole('button', { name: 'New subscription' }).click();

	await page.getByLabel('Endpoint URL').fill('https://new.example.test/hooks');
	await page.getByLabel('Description').fill('Staging listener');
	await page.getByRole('button', { name: 'Create subscription' }).click();

	await expect(page.getByText('Staging listener')).toBeVisible();
});

test('edits a subscription in the same dialog it was created in', async ({ page }) => {
	await page.goto('/webhooks');

	await page.getByRole('article').first().getByRole('button', { name: 'Edit' }).click();
	await expect(page.getByRole('dialog')).toContainText('Edit subscription');

	await page.getByLabel('Description').fill('Renamed listener');
	await page.getByRole('button', { name: 'Save changes' }).click();

	await expect(page.getByText('Renamed listener')).toBeVisible();
});

test('deletes a subscription after confirming', async ({ page }) => {
	await page.goto('/webhooks');

	await page
		.getByRole('article')
		.first()
		.getByRole('button', { name: 'Delete subscription' })
		.click();
	await page
		.getByRole('dialog', { name: 'Delete subscription?' })
		.getByRole('button', { name: 'Delete' })
		.click();

	await expect(page.getByText('Production listener')).toHaveCount(0);
});

test('sends a test event, offering only what the subscription listens for', async ({ page }) => {
	await page.goto('/webhooks');

	const card = page.getByRole('article').first();
	await card.click({ position: { x: 5, y: 5 } });

	// This one filters to three events, so testing anything else would be
	// delivered nowhere and read as a failure.
	const picker = card.getByLabel('Event to send');
	await expect(picker.locator('option')).toHaveCount(3);
	await expect(picker.locator('option', { hasText: 'connection.created' })).toHaveCount(0);

	await card.getByRole('button', { name: 'Send test' }).click();
	await expect(card.getByText(/^Sent —/)).toBeVisible();
});

test('offers every event type where the subscription filters none', async ({ page }) => {
	await page.goto('/webhooks');

	const card = page.getByRole('article').nth(1);
	await card.click({ position: { x: 5, y: 5 } });

	await expect(card.getByLabel('Event to send').locator('option')).toHaveCount(9);
});

test('selects a whole family at once, without that being the group event', async ({ page }) => {
	await page.goto('/webhooks');
	await page.getByRole('button', { name: 'New subscription' }).click();

	const family = page.getByRole('button', { name: /^Heart rate/ });
	await family.click();

	// The group event is its own choice — one event covering the category — so
	// "select all" is a separate control rather than the parent chip.
	await page.getByRole('button', { name: 'Select all' }).click();
	await expect(
		page.getByRole('button', { name: 'series.heart_rate', exact: true })
	).toHaveAttribute('aria-pressed', 'true');
	await expect(page.getByRole('button', { name: 'heart_rate.created' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(family).toContainText('4 of 4');

	await page.getByRole('button', { name: 'Clear all' }).click();
	await expect(
		page.getByRole('button', { name: 'series.heart_rate', exact: true })
	).toHaveAttribute('aria-pressed', 'false');
});

test('keeps exactly the events that were ticked', async ({ page }) => {
	await page.goto('/webhooks');
	await page.getByRole('button', { name: 'New subscription' }).click();

	await page.getByLabel('Endpoint URL').fill('https://picked.test/hooks');
	await page.getByLabel('Description').fill('Picked one');
	await page.getByRole('button', { name: /^Workout/ }).click();
	await page.getByRole('button', { name: 'workout.created' }).click();
	await page.getByRole('button', { name: 'Create subscription' }).click();

	// Not "All events", which is what an empty filter means — and what a dropped
	// selection would look like.
	const card = page.getByRole('article').filter({ hasText: 'Picked one' });
	await expect(card).toContainText('1 event');
	// The folded card names the group; the exact name is in the dialog.
	await expect(card).toContainText('Workout');
});

test('groups deliveries by the day they went out', async ({ page }) => {
	await page.goto('/webhooks/ep_live/deliveries');

	// Forty timestamps in one column is a wall; the question is usually "did
	// anything go out yesterday".
	await expect(page.getByRole('heading', { level: 0 })).toHaveCount(0);
	await expect(page.locator('section').first()).toContainText(/\d{4}/);
	await expect(page.getByText('500').first()).toBeVisible();
});

test('steps through the deliveries and back again', async ({ page }) => {
	await page.goto('/webhooks/ep_live/deliveries');

	// Svix counts nothing, so the bar marks the position and never claims a last
	// page — but it does step both ways.
	const bar = page.getByRole('navigation', { name: 'Pagination' });
	await expect(bar).toContainText('1–20');
	await expect(bar).not.toContainText('of');

	await bar.getByRole('link', { name: 'Next page' }).click();
	await expect(page).toHaveURL(/iterator=20/);
	await expect(bar).toContainText('21–40');

	await bar.getByRole('link', { name: 'Previous page' }).click();
	await expect(bar).toContainText('1–20');
	// Page one is the bare URL, never a backward cursor.
	await expect(page).not.toHaveURL(/iterator=/);
});

test('keeps the test-event picker inside its card, however long the names are', async ({
	page
}) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/webhooks');

	// The second subscription filters nothing, so its picker lists every type —
	// including the longest name the catalogue carries. A `select` sizes itself
	// to its widest option unless it is told not to.
	const card = page.getByRole('article').nth(1);
	await card.click({ position: { x: 5, y: 5 } });

	const box = await card.boundingBox();
	const picker = await card.getByLabel('Event to send').boundingBox();
	expect(picker!.x + picker!.width).toBeLessThanOrEqual(box!.x + box!.width);
});

test('names the groups a subscription listens to, and lists every event when opened', async ({
	page
}) => {
	await page.goto('/webhooks');
	const card = page.getByRole('article').filter({ hasText: 'Production listener' });

	// Folded: a chip per group, and a part of a group says how big a part.
	await expect(card).toContainText('Workout');
	await expect(card).toContainText('Sleep');
	await expect(card.getByText('Heart rate', { exact: true })).toBeVisible();
	await expect(card.getByText('1/3', { exact: true })).toBeVisible();
	await expect(card.getByText('Listens to')).toHaveCount(0);

	await card.click({ position: { x: 5, y: 5 } });
	const list = card.locator('dl');
	await expect(card.getByText('Listens to')).toBeVisible();
	// The label a person reads, with the exact name kept on hover.
	await expect(list.getByText('Heart rate', { exact: true }).last()).toHaveAttribute(
		'title',
		/^series\.heart_rate/
	);
});

test('says an empty filter means every event, later ones included', async ({ page }) => {
	await page.goto('/webhooks');
	const card = page.getByRole('article').filter({ hasText: 'hooks.example.test' });

	await card.click({ position: { x: 5, y: 5 } });
	await expect(
		card.getByText('Every event, including ones added after this was created.')
	).toBeVisible();
});
