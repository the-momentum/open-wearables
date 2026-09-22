import { describe, expect, it } from 'vitest';
import { byGroup, capabilities, filterCapabilities, providerTotals } from './rows';
import type { Coverage } from './types';

const coverage: Coverage = {
	providers: ['garmin', 'oura', 'whoop'],
	timeseries: [
		{
			name: 'Heart',
			metrics: [
				{ code: 'heart_rate', unit: 'bpm', description: 'Beats.', providers: ['garmin', 'oura'] },
				{ code: 'hrv', unit: 'ms', description: '', providers: ['garmin'] }
			]
		},
		{
			name: 'Body',
			metrics: [{ code: 'weight', unit: 'kg', description: '', providers: ['whoop'] }]
		}
	],
	workout_fields: [{ code: 'average_cadence', providers: ['garmin'] }],
	sleep_fields: [{ code: 'deep_sleep_seconds', providers: ['oura'] }],
	menstrual_cycle_fields: [{ code: 'cycle_length', providers: ['garmin'] }],
	health_scores: [{ code: 'sleep', description: '', providers: ['oura', 'whoop'] }]
};

const rows = capabilities(coverage);
const filters = { search: '', layer: '' as const, provider: '', missing: false };

describe('capabilities', () => {
	// The response splits these by the table they land in, which is a backend
	// concern: to a reader they are all "a thing a provider can send".
	it('flattens every layer into one shape', () => {
		expect(rows).toHaveLength(7);
		expect(rows.map((row) => row.layer)).toEqual(
			['timeseries', 'timeseries', 'timeseries', 'workout', 'sleep', 'cycle'].concat('score')
		);
	});

	it('keeps the timeseries category as the group, and names the others', () => {
		expect(rows[0].group).toBe('Heart');
		expect(rows.find((row) => row.layer === 'sleep')?.group).toBe('Sleep fields');
	});

	it('carries the unit and description a metric came with', () => {
		expect(rows[0]).toMatchObject({ unit: 'bpm', description: 'Beats.' });
	});
});

describe('filterCapabilities', () => {
	it('matches a code anywhere in it, ignoring case', () => {
		const hit = filterCapabilities(rows, { ...filters, search: 'RATE' });
		expect(hit.map((row) => row.code)).toEqual(['heart_rate']);
	});

	it('narrows to one layer', () => {
		const hit = filterCapabilities(rows, { ...filters, layer: 'score' });
		expect(hit.map((row) => row.code)).toEqual(['sleep']);
	});

	it('narrows to what one provider can send', () => {
		const hit = filterCapabilities(rows, { ...filters, provider: 'whoop' });
		expect(hit.map((row) => row.code)).toEqual(['weight', 'sleep']);
	});

	// The half of the question the old matrix could not be asked: what an
	// integration cannot deliver decides whether another can stand in for it.
	it('inverts to what a provider cannot send', () => {
		const hit = filterCapabilities(rows, { ...filters, provider: 'whoop', missing: true });
		expect(hit.map((row) => row.code)).toEqual([
			'heart_rate',
			'hrv',
			'average_cadence',
			'deep_sleep_seconds',
			'cycle_length'
		]);
	});

	it('combines a search with a provider', () => {
		const hit = filterCapabilities(rows, { ...filters, provider: 'garmin', search: 'heart' });
		expect(hit.map((row) => row.code)).toEqual(['heart_rate']);
	});
});

describe('providerTotals', () => {
	it('counts the whole matrix per provider, richest first', () => {
		expect(Object.entries(providerTotals(rows))).toEqual([
			['garmin', 4],
			['oura', 3],
			['whoop', 2]
		]);
	});
});

describe('byGroup', () => {
	it('keeps the order the backend chose rather than sorting it', () => {
		expect(byGroup(rows).map((group) => group.group)).toEqual([
			'Heart',
			'Body',
			'Workout fields',
			'Sleep fields',
			'Cycle fields',
			'Health scores'
		]);
	});
});
