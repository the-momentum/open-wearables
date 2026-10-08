import { describe, expect, it } from 'vitest';
import { isNapParam, sessionFilter } from './query';
import { localRange } from '$lib/utils/format';
import { stageLanes, stageRows } from './stages';
import type { SleepSession, StageInterval } from './types';

const interval = (stage: StageInterval['stage'], from: string, to: string): StageInterval => ({
	stage,
	start_time: `2026-09-20T${from}:00Z`,
	end_time: `2026-09-20T${to}:00Z`
});

describe('stageLanes', () => {
	const intervals = [
		interval('light', '23:00', '23:30'),
		interval('deep', '23:30', '23:50'),
		interval('awake', '23:50', '23:55'),
		interval('light', '23:55', '23:59')
	];

	// Awake at the top down to deep, the way a hypnogram is read - not the order
	// the intervals happen to arrive in.
	it('lays the stages out in reading order, not arrival order', () => {
		expect(stageLanes(intervals, () => '').map((lane) => lane.key)).toEqual([
			'awake',
			'light',
			'deep'
		]);
	});

	// An empty lane invites the reader to wonder what belongs in it.
	it('leaves out a stage that never occurred', () => {
		expect(stageLanes(intervals, () => '').some((lane) => lane.key === 'rem')).toBe(false);
	});

	it('gathers every span of one stage into its own lane', () => {
		const light = stageLanes(intervals, () => '').find((lane) => lane.key === 'light');
		expect(light?.spans).toHaveLength(2);
	});

	it('describes a span with the seconds it lasted', () => {
		const seconds: number[] = [];
		stageLanes([interval('deep', '23:30', '23:50')], (_, length) => {
			seconds.push(length);
			return '';
		});
		expect(seconds).toEqual([1200]);
	});
});

describe('stageRows', () => {
	const session = (stages: SleepSession['stages']) => ({ stages }) as SleepSession;

	it('reads minutes as seconds, in the same order as the lanes', () => {
		const rows = stageRows(
			session({ awake_minutes: 20, light_minutes: 200, deep_minutes: 80, rem_minutes: 70 })
		);
		expect(rows.map((row) => [row.label, row.seconds])).toEqual([
			['Awake', 1200],
			['REM', 4200],
			['Light', 12000],
			['Deep', 4800]
		]);
	});

	// A stage nobody spent time in is not a row, and a provider that sent no
	// breakdown at all has no strip.
	it('is empty without a breakdown', () => {
		expect(stageRows(session(null))).toEqual([]);
		expect(
			stageRows(
				session({ awake_minutes: 0, light_minutes: null, deep_minutes: 30, rem_minutes: null })
			).map((row) => row.label)
		).toEqual(['Deep']);
	});
});

describe('localRange', () => {
	// Which end wears the weekday is the caller's call - the range only reports
	// that the two ends differ, and what both days are.
	it('reports the crossing and both days', () => {
		expect(localRange('2026-09-20T20:40:00Z', '2026-09-21T04:20:00Z', '+02:00')).toEqual({
			crosses: true,
			from: '22:40',
			to: '06:20',
			fromDay: 'Sun',
			toDay: 'Mon',
			utc: false
		});
	});

	it('is not crossing when both ends land on one day', () => {
		const range = localRange('2026-09-20T22:40:00Z', '2026-09-21T06:20:00Z', '+02:00');
		expect([range.crosses, range.from, range.to]).toEqual([false, '00:40', '08:20']);
	});

	// A negative offset pulls a session back across midnight, which is the case
	// that produced the original complaint.
	it('handles an offset that moves the night the other way', () => {
		expect(localRange('2026-09-21T04:00:00Z', '2026-09-21T12:00:00Z', '-07:00')).toMatchObject({
			crosses: true,
			from: '21:00',
			to: '05:00',
			fromDay: 'Sun'
		});
	});

	// Suunto stores no offset for sleep at all, so both ends are the stored
	// instant and the card has to say so rather than pass it off as bedtime.
	it('reports when there was no offset to read in', () => {
		expect(localRange('2026-09-20T22:40:00Z', '2026-09-21T06:20:00Z', null).utc).toBe(true);
	});
});

describe('the session filter', () => {
	// Three states for a boolean parameter: leaving it off is how "both" is asked for.
	it('reads the URL, falling back to all', () => {
		expect(sessionFilter(new URLSearchParams('kind=nap'))).toBe('nap');
		expect(sessionFilter(new URLSearchParams('kind=night'))).toBe('night');
		expect(sessionFilter(new URLSearchParams('kind=junk'))).toBe('all');
		expect(sessionFilter(new URLSearchParams())).toBe('all');
	});

	it('asks the API for naps, for night sleep, or for nothing in particular', () => {
		expect(isNapParam('nap')).toBe('true');
		expect(isNapParam('night')).toBe('false');
		expect(isNapParam('all')).toBeNull();
	});
});
