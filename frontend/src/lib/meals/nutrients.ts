import Coffee from '@lucide/svelte/icons/coffee';
import Droplet from '@lucide/svelte/icons/droplet';
import Flame from '@lucide/svelte/icons/flame';
import Gem from '@lucide/svelte/icons/gem';
import Pill from '@lucide/svelte/icons/pill';
import type { Component } from 'svelte';
import type { Part } from '$lib/components/charts/ShareBar.svelte';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { maybe, toFieldGroups, type GroupSpec } from '$lib/events/fields';
import { DASH, showDecimal } from '$lib/utils/format';
import { humanise } from '$lib/utils/text';
import type { Meal } from './types';

type NutrientGroup = { title: string; icon: Component; keys: readonly string[] };

/** Every nutrient series in reading order; a spec keeps it in step with the API's `SeriesType`. */
export const NUTRIENT_GROUPS: readonly NutrientGroup[] = [
	{
		title: 'Energy & macros',
		icon: Flame,
		keys: [
			'dietary_energy_consumed',
			'dietary_energy_from_fat',
			'dietary_protein',
			'dietary_carbohydrates',
			'dietary_sugar',
			'dietary_fiber',
			'dietary_fat_total'
		]
	},
	{
		title: 'Fats',
		icon: Droplet,
		keys: [
			'dietary_fat_saturated',
			'dietary_fat_monounsaturated',
			'dietary_fat_polyunsaturated',
			'dietary_fat_unsaturated',
			'dietary_fat_trans',
			'dietary_cholesterol'
		]
	},
	{
		title: 'Minerals',
		icon: Gem,
		keys: [
			'dietary_sodium',
			'dietary_potassium',
			'dietary_calcium',
			'dietary_iron',
			'dietary_magnesium',
			'dietary_phosphorus',
			'dietary_zinc',
			'dietary_copper',
			'dietary_manganese',
			'dietary_selenium',
			'dietary_chromium',
			'dietary_molybdenum',
			'dietary_iodine',
			'dietary_chloride'
		]
	},
	{
		title: 'Vitamins',
		icon: Pill,
		keys: [
			'dietary_vitamin_a',
			'dietary_vitamin_b6',
			'dietary_vitamin_b12',
			'dietary_vitamin_c',
			'dietary_vitamin_d',
			'dietary_vitamin_e',
			'dietary_vitamin_k',
			'dietary_thiamin',
			'dietary_riboflavin',
			'dietary_niacin',
			'dietary_folate',
			'dietary_folic_acid',
			'dietary_pantothenic_acid',
			'dietary_biotin'
		]
	},
	{ title: 'Other', icon: Coffee, keys: ['dietary_caffeine', 'hydration'] }
];

const LABELS: Record<string, string> = {
	dietary_energy_consumed: 'Energy',
	dietary_fat_total: 'Total fat',
	dietary_fat_saturated: 'Saturated',
	dietary_fat_monounsaturated: 'Monounsaturated',
	dietary_fat_polyunsaturated: 'Polyunsaturated',
	dietary_fat_unsaturated: 'Unsaturated',
	dietary_fat_trans: 'Trans',
	hydration: 'Water'
};

export const nutrientLabel = (key: string): string =>
	LABELS[key] ??
	humanise(key.replace(/^dietary_/, '')).replace(
		/^Vitamin (\w+)$/,
		(_, id: string) => `Vitamin ${id.toUpperCase()}`
	);

export const formatAmount = (value: number | null | undefined, unit: string): string =>
	value === null || value === undefined ? DASH : `${showDecimal(value)} ${unit}`;

export const nutrientGroups = (meal: Meal): FieldGroup[] =>
	toFieldGroups(
		NUTRIENT_GROUPS.map(({ title, icon, keys }): GroupSpec => [
			title,
			icon,
			keys.map((key) => [
				nutrientLabel(key),
				maybe(meal.nutrients[key], ({ value, unit }) => formatAmount(value, unit))
			])
		])
	);

/** Where the energy comes from, at 4/4/9 kcal per gram of protein, carbs and fat; empty without macros. */
export function macroEnergy(meal: Meal): Part[] {
	const { protein_g, carbohydrates_g, fat_g } = meal.macros ?? {};
	const parts = [
		{ key: 'protein', label: 'Protein', value: Math.round((protein_g ?? 0) * 4) },
		{ key: 'carbs', label: 'Carbs', value: Math.round((carbohydrates_g ?? 0) * 4) },
		{ key: 'fat', label: 'Fat', value: Math.round((fat_g ?? 0) * 9) }
	];
	return parts.some((part) => part.value > 0) ? parts : [];
}
