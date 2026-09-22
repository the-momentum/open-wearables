import { collect } from '$lib/utils/collect';
import { humanise } from '$lib/utils/text';
import type { EventType } from './types';

export type EventGroup = {
	label: string;
	/** The one event that stands for the whole group, where there is one. */
	parent: EventType | null;
	events: EventType[];
};

/**
 * The API answers with one flat list of eighty-odd names. Two shapes hide in it:
 * a time-series group event carries its granular `series.*` children, and
 * everything else falls into a family by the word before the dot.
 */
export function groupEvents(types: EventType[]): EventGroup[] {
	const parents = types.filter((type) => type.child_events?.length);
	const children = new Set(parents.flatMap((type) => type.child_events ?? []));
	const byName = new Map(types.map((type) => [type.name, type]));

	const loose = types.filter((type) => !children.has(type.name) && !type.child_events?.length);

	const families = [...collect(loose, (type) => type.name.split('.')[0]).entries()].map(
		([family, events]) => ({ label: humanise(family), parent: null, events })
	);

	const series = parents.map((parent) => ({
		label: humanise(parent.name.replace(/\.created$/, '')),
		parent,
		// A child the list never declared would be a name with nothing behind it.
		events: (parent.child_events ?? [])
			.map((name) => byName.get(name))
			.filter((type): type is EventType => type !== undefined)
	}));

	return [...families, ...series];
}

/** Everything a group can put in the filter, the standing-in event included. */
export const namesIn = (group: EventGroup): string[] => [
	...(group.parent ? [group.parent.name] : []),
	...group.events.map((event) => event.name)
];
