import { page, userEvent } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import Hint from './Hint.svelte';
// The bubble's box and colours are Tailwind's.
import '../../../app.css';

describe('Hint', () => {
	it('opens on a tap, where hover never fires, and Escape closes it', async () => {
		await render(Hint, { label: 'Garmin: expired', text: 'Authorisation expired' });

		const trigger = page.getByRole('button', { name: 'Garmin: expired' });
		const bubble = page.getByRole('tooltip', { includeHidden: true });
		await expect.element(trigger).toHaveAccessibleDescription('Authorisation expired');
		await expect.element(bubble).not.toBeVisible();

		await trigger.click();
		await expect.element(bubble).toBeVisible();

		await userEvent.keyboard('{Escape}');
		await expect.element(bubble).not.toBeVisible();
	});

	// WCAG 1.4.13: a bubble that keyboard focus opened must close without
	// moving focus off its trigger.
	it('hides on Escape while its trigger keeps focus', async () => {
		await render(Hint, { label: 'Scopes', text: 'heartrate' });

		await userEvent.tab();
		const bubble = page.getByRole('tooltip', { includeHidden: true });
		await expect.element(bubble).toBeVisible();

		await userEvent.keyboard('{Escape}');
		await expect.element(bubble).not.toBeVisible();
		await expect.element(page.getByRole('button', { name: 'Scopes' })).toHaveFocus();
	});
});
