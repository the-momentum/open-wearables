import { isPartial, sumOf } from '$lib/events/totals';
import type { Meal } from './types';

export type MealTotals = {
	count: number;
	calories: number | null;
	/** A meal carries no zone offset, so these are UTC days. */
	caloriesPerDay: number | null;
	protein: number | null;
	partial: boolean;
};

export function sumMeals(meals: Meal[], total: number | null, hasMore: boolean): MealTotals {
	const calories = sumOf(meals, (meal) => meal.calories_kcal);
	const days = new Set(meals.map((meal) => meal.timestamp.slice(0, 10))).size;

	return {
		count: total ?? meals.length,
		calories,
		caloriesPerDay: calories === null ? null : calories / days,
		protein: sumOf(meals, (meal) => meal.macros?.protein_g),
		partial: isPartial(hasMore)
	};
}
