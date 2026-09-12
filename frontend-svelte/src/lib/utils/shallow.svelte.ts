import { pushState } from '$app/navigation';
import { page } from '$app/state';
import { withParams } from './url';

/**
 * URL-visible state that must not re-run a load. `pushState` leaves `page.url`
 * on the loaded page, so the value lives in `page.state`, which back and
 * forward restore; the query string is read only on arrival.
 */
export function shallowParam(key: string, stateKey: keyof App.PageState) {
	return {
		get current(): string {
			const held = page.state[stateKey];
			return typeof held === 'string' ? held : (page.url.searchParams.get(key) ?? '');
		},
		set(value: string) {
			// eslint-disable-next-line svelte/no-navigation-without-resolve -- built from page.url
			pushState(withParams(page.url, { [key]: value || null }), {
				...page.state,
				[stateKey]: value
			});
		}
	};
}
