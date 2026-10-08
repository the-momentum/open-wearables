import { navigating } from '$app/state';

/** Short enough to feel instant; anything quicker should not flash a loader. */
const SLOW_AFTER_MS = 150;

/** Where a navigation is headed, once it has taken long enough to show. */
export function slowNavigation() {
	let target = $state<URL | null>(null);

	$effect(() => {
		const next = navigating.to?.url;
		if (!next) {
			target = null;
			return;
		}
		const timer = setTimeout(() => (target = next), SLOW_AFTER_MS);
		return () => clearTimeout(timer);
	});

	return {
		get target() {
			return target;
		}
	};
}
