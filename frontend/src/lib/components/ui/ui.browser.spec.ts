import { page, userEvent } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import DateField from './DateField.svelte';
import DateRangeField from './DateRangeField.svelte';
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

// The test browser has a mouse, so these are the drawn pickers, not native inputs.
describe('DateField', () => {
	it('commits a typed day on Enter, never a year half typed', async () => {
		const onchange = vi.fn();
		await render(DateField, { label: 'Day', value: '2026-11-14', onchange });

		await page.getByRole('spinbutton', { name: /^year/ }).click();
		await userEvent.keyboard('20');
		await userEvent.keyboard('25');
		expect(onchange).not.toHaveBeenCalled();

		await userEvent.keyboard('{Enter}');
		expect(onchange).toHaveBeenCalledExactlyOnceWith('2025-11-14');
	});

	it('commits a day picked in the calendar', async () => {
		const onchange = vi.fn();
		await render(DateField, { label: 'Day', value: '2026-11-14', onchange });

		await page.getByRole('button', { name: 'Open calendar' }).click();
		await page.getByRole('button', { name: /, 3 November 2026/ }).click();
		await expect.poll(() => onchange.mock.calls).toEqual([['2026-11-03']]);
	});

	it('drops a typed day past its bound', async () => {
		const onchange = vi.fn();
		await render(DateField, { label: 'Day', value: '2026-11-14', max: '2026-11-21', onchange });

		await page.getByRole('spinbutton', { name: /^year/ }).click();
		await userEvent.keyboard('2027{Enter}');
		expect(onchange).not.toHaveBeenCalled();
	});
});

describe('DateRangeField', () => {
	it('commits a range once both ends are picked, not after the first', async () => {
		const onchange = vi.fn();
		await render(DateRangeField, {
			label: 'Date range',
			from: '2026-10-10',
			to: '2026-11-14',
			onchange
		});

		await page.getByRole('button', { name: 'Open calendar' }).click();
		await page.getByRole('button', { name: /, 5 October 2026/ }).click();
		expect(onchange).not.toHaveBeenCalled();

		await page.getByRole('button', { name: /, 20 October 2026/ }).click();
		await expect
			.poll(() => onchange.mock.calls)
			.toEqual([[{ from: '2026-10-05', to: '2026-10-20' }]]);
	});

	it('drops a typed end that falls before the start', async () => {
		const onchange = vi.fn();
		await render(DateRangeField, {
			label: 'Date range',
			from: '2026-10-10',
			to: '2026-11-14',
			onchange
		});

		const end = page.getByRole('group', { name: 'To' });
		await end.getByRole('spinbutton', { name: /^month/ }).click();
		await userEvent.keyboard('09{Enter}');
		expect(onchange).not.toHaveBeenCalled();
	});
});
