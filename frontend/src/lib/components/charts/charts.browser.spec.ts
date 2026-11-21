import { describe, expect, it } from 'vitest';
import { userEvent } from 'vitest/browser';
import { render } from 'vitest-browser-svelte';
import DonutChart from './DonutChart.svelte';
import IntervalChart from './IntervalChart.svelte';

describe('IntervalChart', () => {
	// Copies of a night that differ in where a stage ends start their spans at the same time
	it('draws spans of one lane that share a start', async () => {
		const chart = await render(IntervalChart, {
			rows: [
				{
					key: 'light',
					label: 'Light',
					shade: 'bg-primary',
					spans: [
						{ start: 0, end: 600, title: 'first' },
						{ start: 0, end: 900, title: 'second' }
					]
				}
			],
			from: 0,
			to: 900,
			formatTime: String,
			label: 'Sleep stages'
		});

		expect(
			chart.container.querySelectorAll('span[title="first"], span[title="second"]')
		).toHaveLength(2);
	});
});

describe('DonutChart', () => {
	// The slice and its legend row are found by the same key: pointing at one has to light both.
	it('dims every other slice while a legend row is pointed at', async () => {
		const chart = await render(DonutChart, {
			parts: [
				{ key: 'garmin', label: 'Garmin', value: 3 },
				{ key: 'oura', label: 'Oura', value: 1 }
			],
			total: 5,
			caption: 'connections',
			label: 'Connections per provider'
		});
		const slices = () =>
			[...chart.container.querySelectorAll('path')].map((path) => path.classList);

		await userEvent.hover(chart.getByText('Oura'));
		expect(slices().map((list) => list.contains('opacity-30'))).toEqual([true, false, true]);

		await userEvent.unhover(chart.getByText('Oura'));
		expect(slices().some((list) => list.contains('opacity-30'))).toBe(false);
	});
});
