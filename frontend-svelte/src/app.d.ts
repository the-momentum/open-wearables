import type { AuthContext } from '$lib/server/auth';

declare global {
	namespace App {
		interface Locals {
			auth: AuthContext;
		}

		interface PageState {
			/** Which provider the recent-sync list is narrowed to; '' means all. */
			syncProvider?: string;
		}
	}
}

export {};
