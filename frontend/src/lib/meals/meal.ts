import { humanise } from '$lib/utils/text';
import type { Meal } from './types';

/** Providers send the type lower or upper case (`BEFORE_DINNER` from Google). */
export const mealTypeLabel = (mealType: string | null): string | null =>
	mealType ? humanise(mealType.toLowerCase()) : null;

export const mealTitle = (meal: Meal): string =>
	meal.name ?? mealTypeLabel(meal.meal_type) ?? 'Meal';
