import type { AuthContext } from '$lib/server/auth';

declare global {
	namespace App {
		interface Locals {
			auth: AuthContext;
		}

		/** Filters that are URL-visible but must not re-run a load. */
		interface PageState {
			syncProvider?: string;
			summaryProvider?: string;
		}
	}
}

export {};
