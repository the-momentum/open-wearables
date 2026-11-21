import { untrack } from 'svelte';
import { navigating, page } from '$app/state';

/**
 * Data a component fetches for itself, because the page load has no business
 * waiting for it - a chart nobody expanded, figures nobody has scrolled to.
 *
 * The URL is a function so the caller's reactive reads happen inside the effect:
 * pass the string and it is read once, at setup, and never refetched.
 *
 * It refetches when that URL changes, and when the page's data is invalidated -
 * a deletion has to show in the totals beside the list. A navigation that leaves
 * the URL as it was does not: clicking the tab you are on, or stepping to the
 * next page of a list the figures do not depend on, must not blank them.
 */
export function resource<T>(url: () => string, fallback: T | null = null) {
	let value = $state<T | null>(fallback);
	let settled = $state(false);

	// Derived, so a recomputed but identical string does not count as a change.
	const target = $derived(url());
	let shown: string | null = null;
	// Requests are told apart by number rather than by the effect's teardown: a
	// run that keeps what is on screen must not orphan a request still in flight.
	let latest = 0;
	let gone = false;

	$effect(() => {
		const next = target;
		// An invalidation reloads the page's data without navigating; that is the
		// one time an unchanged URL is worth asking again.
		void page.data;
		if (next === shown && untrack(() => navigating.to)) return;

		shown = next;
		const request = ++latest;
		const current = () => !gone && request === latest;
		value = fallback;
		settled = false;

		fetch(next)
			.then((response) => (response.ok ? response.json() : null))
			.then((body: T | null) => {
				if (current() && body !== null) value = body;
			})
			.catch(() => undefined)
			.finally(() => {
				if (current()) settled = true;
			});
	});

	// A card closed mid-flight must not write into a component that is gone.
	$effect(() => () => {
		gone = true;
	});

	return {
		get current() {
			return value;
		},
		/** False until the request has finished, however it finished. */
		get settled() {
			return settled;
		}
	};
}
