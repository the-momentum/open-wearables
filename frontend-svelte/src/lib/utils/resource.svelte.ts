/**
 * Data a component fetches for itself, because the page load has no business
 * waiting for it — a chart nobody expanded, figures nobody has scrolled to.
 *
 * The URL is a function so the caller's reactive reads happen inside the effect:
 * pass the string and it is read once, at setup, and never refetched.
 */
export function resource<T>(url: () => string, fallback: T | null = null) {
	let value = $state<T | null>(fallback);
	let settled = $state(false);

	$effect(() => {
		const target = url();
		let live = true;
		value = fallback;
		settled = false;

		fetch(target)
			.then((response) => (response.ok ? response.json() : null))
			.then((body: T | null) => {
				if (live && body !== null) value = body;
			})
			.catch(() => undefined)
			.finally(() => {
				if (live) settled = true;
			});

		// A card closed mid-flight must not write into a component that is gone.
		return () => {
			live = false;
		};
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
