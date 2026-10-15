import { describe, expect, it } from 'vitest';
import { detailGroups } from './fields';
import { currentDay, cycleDays, fertileWindow, phaseLabel, phaseSpans } from './phases';
import { sumCycles } from './totals';
import type { Cycle } from './types';

const cycle = (over: Partial<Cycle> = {}): Cycle =>
	({
		id: 'c1',
		start_time: '2026-09-10T00:00:00Z',
		end_time: '2026-10-06T00:00:00Z',
		zone_offset: null,
		source: { provider: 'oura', source: 'oura', device: null, device_type: 'ring' },
		current_phase: 4,
		current_phase_type: 'luteal',
		day_in_cycle: 26,
		cycle_length: 26,
		predicted_cycle_length: 26,
		is_predicted_cycle: false,
		period_length: 4,
		length_of_current_phase: 13,
		days_until_next_phase: 0,
		fertile_window_start: 8,
		length_of_fertile_window: 6,
		last_updated_at: '2026-10-06T06:00:00Z',
		has_specified_cycle_length: true,
		has_specified_period_length: true,
		pregnancy_snapshot: null,
		...over
	}) as Cycle;

describe('fertileWindow', () => {
	// Inclusive: a window starting on day 8 and six days long ends on day 13, not
	// day 14. The bar and the detail column both read it from here, because the
	// arithmetic was written twice and is the kind that goes wrong once.
	it('counts the window inclusively', () => {
		expect(fertileWindow(cycle())).toEqual({ from: 8, to: 13 });
	});

	it('has no window without both ends of one', () => {
		expect(fertileWindow(cycle({ length_of_fertile_window: null }))).toBeNull();
		expect(fertileWindow(cycle({ fertile_window_start: null }))).toBeNull();
	});
});

describe('phaseSpans', () => {
	it('lays the phases end to end across the cycle', () => {
		expect(phaseSpans(cycle())).toEqual([
			{ phase: 'menstruation', label: 'Period', shade: expect.any(String), from: 1, to: 4 },
			{ phase: 'follicular', label: 'Follicular', shade: expect.any(String), from: 5, to: 7 },
			{ phase: 'ovulation', label: 'Fertile', shade: expect.any(String), from: 8, to: 13 },
			{ phase: 'luteal', label: 'Luteal', shade: expect.any(String), from: 14, to: 26 }
		]);
	});

	// Follicular and luteal are only what is left either side of the fertile
	// window, so without one they cannot be told apart and are not invented.
	it('draws the period alone when the fertile window is unknown', () => {
		const spans = phaseSpans(cycle({ fertile_window_start: null, length_of_fertile_window: null }));
		expect(spans.map((span) => span.phase)).toEqual(['menstruation']);
	});

	it('draws a predicted cycle against the length it is predicted to run', () => {
		const predicted = cycle({ cycle_length: null, predicted_cycle_length: 28 });
		expect(cycleDays(predicted)).toBe(28);
		expect(phaseSpans(predicted).at(-1)).toMatchObject({ phase: 'luteal', to: 28 });
	});

	it('has nothing to draw with no length at all', () => {
		expect(phaseSpans(cycle({ cycle_length: null, predicted_cycle_length: null }))).toEqual([]);
	});
});

describe('currentDay', () => {
	const now = new Date('2026-09-22T12:00:00Z').getTime();

	it('marks today only while the cycle is still running', () => {
		expect(currentDay(cycle({ day_in_cycle: 13 }), now)).toBe(13);
	});

	// A closed cycle's `day_in_cycle` is where it ended, which is not a place to
	// put a marker saying "today".
	it('marks nothing on a cycle that has closed', () => {
		const old = cycle({ start_time: '2026-01-01T00:00:00Z', end_time: '2026-01-27T00:00:00Z' });
		expect(currentDay(old, now)).toBeNull();
	});

	it('marks nothing on a cycle that has not happened yet', () => {
		expect(currentDay(cycle({ is_predicted_cycle: true }), now)).toBeNull();
	});
});

describe('sumCycles', () => {
	// A predicted length is the provider's forecast; averaging it in would make
	// the figure describe the model rather than the person.
	it('averages the cycles that were lived, not the predicted one', () => {
		const totals = sumCycles(
			[
				cycle({ cycle_length: 26, period_length: 4 }),
				cycle({ cycle_length: 30, period_length: 6 }),
				cycle({ cycle_length: null, predicted_cycle_length: 99, is_predicted_cycle: true })
			],
			3,
			false
		);

		expect([totals.averageLength, totals.averagePeriod]).toEqual([28, 5]);
		expect(totals.count).toBe(3);
	});
});

describe('detailGroups', () => {
	// A forecast that repeats the measured length is a row carrying nothing.
	it('drops the predicted length where it matches the measured one', () => {
		const labels = (over: Partial<Cycle>) =>
			detailGroups(cycle(over))
				.flatMap((group) => group.fields)
				.map((field) => field.label);

		expect(labels({ predicted_cycle_length: 26 })).not.toContain('Predicted length');
		expect(labels({ predicted_cycle_length: 29 })).toContain('Predicted length');
	});

	it('spells the fertile window as the days it covers', () => {
		const fields = detailGroups(cycle()).flatMap((group) => group.fields);
		expect(fields).toContainEqual({ label: 'Fertile window', value: 'Day 8–13' });
	});

	// The difference between a record and an estimate is worth a word.
	it("says whether a length was the person's own or a guess", () => {
		const told = (specified: boolean) =>
			detailGroups(cycle({ has_specified_cycle_length: specified }))
				.flatMap((group) => group.fields)
				.find((field) => field.label === 'Cycle length')?.value;

		expect(told(true)).toBe('The user');
		expect(told(false)).toBe('Estimated');
	});

	it('drops a group the provider had nothing for', () => {
		const bare = cycle({ period_length: null, fertile_window_start: null });
		expect(detailGroups(bare).map((group) => group.title)).not.toContain('Period');
	});
});

describe('phaseLabel', () => {
	it('reads the provider vocabulary, whichever word it used', () => {
		expect(phaseLabel('menstrual')).toBe('Period');
		expect(phaseLabel('MENSTRUATION')).toBe('Period');
		expect(phaseLabel('ovulation')).toBe('Fertile');
	});

	it('renders a phase it has never seen rather than dropping it', () => {
		expect(phaseLabel('early_follicular')).toBe('Early follicular');
	});

	it('has nothing to say for a cycle with no phase', () => {
		expect(phaseLabel(null)).toBeNull();
	});
});
