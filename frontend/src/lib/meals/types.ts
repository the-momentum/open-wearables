import type { SourceMetadata } from '$lib/events/types';

/** Mirrors backend `NutrientValue`: a value in its series' unit. */
export type NutrientValue = { value: number; unit: string };

/** Mirrors backend `Macros`. */
export type Macros = {
	protein_g: number | null;
	carbohydrates_g: number | null;
	fat_g: number | null;
	fiber_g: number | null;
};

/**
 * Mirrors backend `Meal`. It carries no zone offset, so its time can only be
 * shown in UTC. `nutrients` is keyed by series type (`dietary_protein`, ...).
 */
export type Meal = {
	id: string;
	timestamp: string;
	meal_type: string | null;
	name: string | null;
	source: SourceMetadata;
	calories_kcal: number | null;
	macros: Macros | null;
	water_ml: number | null;
	nutrients: Record<string, NutrientValue>;
};

export type MealPage = {
	data: Meal[];
	pagination: {
		next_cursor: string | null;
		previous_cursor: string | null;
		has_more: boolean;
		total_count: number | null;
	};
};
