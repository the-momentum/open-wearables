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

/** What a card says about names the catalogue dropped, as chip tooltip and as list hint. */
export const strayNote = (count: number) =>
	`The API no longer sends ${count === 1 ? 'this event' : 'these events'}, so nothing will arrive. Edit the subscription to remove or replace ${count === 1 ? 'it' : 'them'}.`;

export type EventSummary = {
	label: string;
	/** Nothing in the group is left out: its group event, or every event of a family. */
	whole: boolean;
	/** The group event itself, where it is in the filter — one event for the lot. */
	groupEvent: EventType | null;
	/** The chosen events, in the fewest words that still tell them apart. */
	items: { label: string; name: string; description: string }[];
	/** How many events the group has, so a part of it can say how big a part. */
	total: number;
	/** Names the catalogue no longer has: not a group, something to edit out. */
	stray: boolean;
};

/**
 * `series.garmin_stress_level.created` as "Garmin stress level": almost every
 * event ends in `.created`, and a series child already sits under its group.
 * Other verbs are kept, since "revoked" and "created" are different events.
 */
function shortLabel(event: EventType, group: EventGroup): string {
	if (group.parent) return humanise(event.name.replace(/^series\./, '').replace(/\.created$/, ''));
	return humanise(event.name.split('.').at(-1) ?? event.name);
}

/**
 * A subscription's filter read the way the picker groups it. A name the
 * catalogue no longer has is kept, and said to be no longer sent, rather than
 * dropped: the subscription still holds it, and nothing will ever arrive for it.
 */
export function summarise(names: string[], types: EventType[]): EventSummary[] {
	const chosen = new Set(names);

	const known = groupEvents(types).flatMap((group) => {
		const events = group.events.filter((event) => chosen.has(event.name));
		const groupEvent = group.parent && chosen.has(group.parent.name) ? group.parent : null;
		if (!groupEvent && events.length === 0) return [];

		return [
			{
				label: group.label,
				whole: group.parent ? groupEvent !== null : events.length === group.events.length,
				groupEvent,
				items: events.map((event) => ({
					label: shortLabel(event, group),
					name: event.name,
					description: event.description
				})),
				total: group.events.length,
				stray: false
			}
		];
	});

	const catalogued = new Set(types.map((type) => type.name));
	const stray = names.filter((name) => !catalogued.has(name));
	const other = stray.length
		? [
				{
					label: 'No longer sent',
					whole: false,
					groupEvent: null,
					items: stray.map((name) => ({ label: name, name, description: '' })),
					total: stray.length,
					stray: true
				}
			]
		: [];

	return [...known, ...other];
}
