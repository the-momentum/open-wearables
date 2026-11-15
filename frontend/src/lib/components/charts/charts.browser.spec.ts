import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import IntervalChart from './IntervalChart.svelte';

describe('IntervalChart', () => {
	// Copies of a night that differ in where a stage ends start their spans at the same time
	it('draws spans of one lane that share a start', () => {
		const chart = render(IntervalChart, {
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

		expect(chart.container.querySelectorAll('span[title]')).toHaveLength(2);
	});
});
