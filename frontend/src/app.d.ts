import type { AuthContext } from '$lib/server/auth';
import type { Theme } from '$lib/theme';

declare global {
	const __APP_VERSION__: string;

	namespace App {
		interface Locals {
			auth: AuthContext;
			theme: Theme;
		}

		/** Filters that are URL-visible but must not re-run a load. */
		interface PageState {
			syncProvider?: string;
		}
	}
}

export {};
