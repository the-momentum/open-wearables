import type { Component } from 'svelte';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';

/**
 * Format a reading, or keep the null that says the provider sent none — which
 * is what `toFieldGroups` drops the field on.
 */
export const maybe = <T>(
	value: T | null | undefined,
	format: (value: T) => string
): string | null => (value === null || value === undefined ? null : format(value));

/** A group before the empty entries are dropped: `null` means the provider sent none. */
export type GroupSpec = [string, Component, [string, string | null][]];

/**
 * Drops absent fields, then groups left with nothing. On a card's summary row a
 * dash says "this provider sent nothing", but a column of them says nothing at
 * all — so the detail columns show only what arrived.
 */
export const toFieldGroups = (groups: GroupSpec[]): FieldGroup[] =>
	groups
		.map(([title, icon, entries]) => ({
			title,
			icon,
			fields: entries
				.filter((entry): entry is [string, string] => entry[1] !== null)
				.map(([label, value]) => ({ label, value }))
		}))
		.filter((group) => group.fields.length > 0);
