import { describe, expect, it } from 'vitest';
import { groupByProvider, rankSources, sourceDetail, sourceTitle } from './sources';
import type { DataSource } from './types';

const source = (overrides: Partial<DataSource>): DataSource => ({
	id: crypto.randomUUID(),
	provider: 'garmin',
	device_model: null,
	device_name: null,
	device_type: null,
	source: null,
	software_version: null,
	...overrides
});

const PROVIDERS = [
	{ provider: 'oura', priority: 1 },
	{ provider: 'garmin', priority: 2 }
];
const DEVICE_TYPES = [
	{ device_type: 'watch', priority: 1 },
	{ device_type: 'ring', priority: 2 }
];

describe('rankSources', () => {
	it('orders by provider, then device type, then device model', () => {
		const ranked = rankSources(
			[
				source({ provider: 'garmin', device_type: null, device_model: null }),
				source({ provider: 'garmin', device_type: 'watch', device_model: 'Garmin fenix 8' }),
				source({ provider: 'garmin', device_type: 'watch', device_model: 'Garmin Edge 840' }),
				source({ provider: 'oura', device_type: 'ring' })
			],
			PROVIDERS,
			DEVICE_TYPES
		);

		expect(ranked.map((entry) => [entry.provider, entry.device_model])).toEqual([
			['oura', null],
			['garmin', 'Garmin Edge 840'],
			['garmin', 'Garmin fenix 8'],
			['garmin', null]
		]);
	});

	it('puts a provider or device type missing from the lists last', () => {
		const ranked = rankSources(
			[source({ provider: 'whoop', device_type: 'band' }), source({ provider: 'garmin' })],
			PROVIDERS,
			DEVICE_TYPES
		);

		expect(ranked.map((entry) => entry.provider)).toEqual(['garmin', 'whoop']);
	});
});

describe('groupByProvider', () => {
	it('keeps the ranked order inside and between groups', () => {
		const ranked = rankSources(
			[
				source({ provider: 'garmin', device_type: 'watch' }),
				source({ provider: 'oura', device_type: 'ring' }),
				source({ provider: 'garmin' })
			],
			PROVIDERS,
			DEVICE_TYPES
		);

		const groups = groupByProvider(ranked);

		expect(groups.map((group) => [group.provider, group.sources.length])).toEqual([
			['oura', 1],
			['garmin', 2]
		]);
		expect(groups[1].sources[0].device_type).toBe('watch');
	});
});

describe('source labels', () => {
	it('names a source with no model as account-level data', () => {
		expect(sourceTitle(source({ device_name: 'Apple Watch Series 6' }))).toBe(
			'Apple Watch Series 6'
		);
		expect(sourceTitle(source({}))).toBe('No device reported');
	});

	it.each([
		['garmin', null],
		['google_health_api', null],
		['Apple Watch Series 6', null],
		["Kuba's Apple Watch", "Kuba's Apple Watch"],
		['com.fitbit.FitbitMobile', 'com.fitbit.FitbitMobile'],
		['  ', null]
	])('shows the source name %j only when it adds something', (name, expected) => {
		expect(sourceDetail(source({ source: name, device_name: 'Apple Watch Series 6' }))).toBe(
			expected
		);
	});
});
