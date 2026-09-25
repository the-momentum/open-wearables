import Activity from '@lucide/svelte/icons/activity';
import Bike from '@lucide/svelte/icons/bike';
import Dumbbell from '@lucide/svelte/icons/dumbbell';
import Flower from '@lucide/svelte/icons/flower';
import Footprints from '@lucide/svelte/icons/footprints';
import Mountain from '@lucide/svelte/icons/mountain';
import Sailboat from '@lucide/svelte/icons/sailboat';
import Snowflake from '@lucide/svelte/icons/snowflake';
import WavesLadder from '@lucide/svelte/icons/waves-ladder';
import type { Component } from 'svelte';

/**
 * Keyed by what the slug contains, not by the slug itself: `WorkoutType` has
 * some eighty members and grows, and an icon is not worth a list that has to be
 * revisited every time the backend adds a sport. Anything unmatched gets the
 * generic mark, which is a fair answer for `other` too.
 *
 * Order decides ties — `mountain_biking` is cycling, not mountaineering.
 */
const KINDS: [RegExp, Component][] = [
	[/cycl|bik/, Bike],
	[/swim/, WavesLadder],
	[/ski|snow|skat|sled/, Snowflake],
	[/row|kayak|canoe|paddl|surf|sail|boat/, Sailboat],
	[/yoga|pilates|stretch|medit|breath/, Flower],
	[/strength|weight|fitness|elliptical|stair|cardio|gym/, Dumbbell],
	[/hik|mountain|climb/, Mountain],
	[/run|walk|tread|jog|hiit/, Footprints]
];

export function workoutIcon(type: string): Component {
	const slug = type.toLowerCase();
	return KINDS.find(([pattern]) => pattern.test(slug))?.[1] ?? Activity;
}
