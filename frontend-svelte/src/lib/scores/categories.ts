import Activity from '@lucide/svelte/icons/activity';
import BatteryCharging from '@lucide/svelte/icons/battery-charging';
import Dumbbell from '@lucide/svelte/icons/dumbbell';
import Flame from '@lucide/svelte/icons/flame';
import HeartPulse from '@lucide/svelte/icons/heart-pulse';
import Moon from '@lucide/svelte/icons/moon';
import Shield from '@lucide/svelte/icons/shield';
import Trophy from '@lucide/svelte/icons/trophy';
import Zap from '@lucide/svelte/icons/zap';
import type { Component } from 'svelte';
import { DASH, formatDecimal, showDecimal } from '$lib/utils/format';
import { humanise } from '$lib/utils/text';
import type { HealthScore } from './types';

export type CategorySpec = {
	label: string;
	icon: Component;
	/**
	 * Where the readable score lives, when `value` is not it. Only resilience
	 * needs this: `fill_missing_resilience_scores_task` stores the HRV
	 * coefficient of variation in `value` and the 0-100 score beside it.
	 */
	scoreComponent?: string;
	/** What `value` then holds instead, so the raw number can still be shown. */
	rawLabel?: string;
	rawFormat?: (value: number) => string;
};

/** Backend `HealthScoreCategory`, in the order the tab reads them. */
const CATEGORIES: Record<string, CategorySpec> = {
	sleep: { label: 'Sleep', icon: Moon },
	recovery: { label: 'Recovery', icon: HeartPulse },
	readiness: { label: 'Readiness', icon: Zap },
	activity: { label: 'Activity', icon: Activity },
	stress: { label: 'Stress', icon: Flame },
	body_battery: { label: 'Body battery', icon: BatteryCharging },
	strain: { label: 'Strain', icon: Dumbbell },
	resilience: {
		label: 'Resilience',
		icon: Shield,
		scoreComponent: 'resilience_score',
		rawLabel: 'HRV variability',
		rawFormat: (value) => `${(value * 100).toFixed(1)}%`
	}
};

/**
 * Only these can be sent as a filter: the API takes a `HealthScoreCategory`
 * enum and 422s the whole page on anything else.
 */
export const knownCategory = (category: string) => category in CATEGORIES;

/** A row with no provider is a broken row, not a reason to drop the reading. */
export const providerOf = (score: HealthScore) => score.provider ?? 'unknown';

/** A category the backend grew since this shipped still has to render. */
export const categorySpec = (category: string): CategorySpec =>
	CATEGORIES[category] ?? { label: humanise(category), icon: Trophy };

export const categoryLabel = (category: string) => categorySpec(category).label;

const RANK = Object.keys(CATEGORIES);

/** Known categories first in their own order, anything newer alphabetically after. */
export function byCategory(left: string, right: string): number {
	const [a, b] = [RANK.indexOf(left), RANK.indexOf(right)];
	if (a === -1 && b === -1) return left.localeCompare(right);
	if (a === -1) return 1;
	if (b === -1) return -1;
	return a - b;
}

/**
 * The number a reader means by "the score". For resilience that is a component,
 * not `value` — showing 0.157 as a resilience score is showing the wrong number.
 */
export function scoreOf(score: HealthScore): number | null {
	const { scoreComponent } = categorySpec(score.category);
	if (!scoreComponent) return score.value;
	return score.components?.[scoreComponent]?.value ?? null;
}

/** `value` under its own name, where it is not the score. Null when it is. */
export function rawReading(score: HealthScore): { label: string; value: string } | null {
	const spec = categorySpec(score.category);
	if (!spec.scoreComponent || !spec.rawLabel || score.value === null) return null;

	return {
		label: spec.rawLabel,
		value: spec.rawFormat?.(score.value) ?? showDecimal(score.value, 2)
	};
}

/** Components, minus whichever one the card is already showing as the score. */
export function componentsOf(score: HealthScore): { label: string; value: string }[] {
	const { scoreComponent } = categorySpec(score.category);

	return Object.entries(score.components ?? {})
		.filter(([key]) => key !== scoreComponent)
		.map(([key, component]) => ({
			label: humanise(key),
			// A component can be a rating with no number of its own — Suunto's
			// stress state arrives as both, Oura's metric type as a word only.
			value:
				[formatDecimal(component.value), component.qualifier].filter(Boolean).join(' · ') || DASH
		}));
}
