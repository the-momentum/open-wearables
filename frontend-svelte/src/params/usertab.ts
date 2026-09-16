import { USER_TAB_SLUGS } from '$lib/users/tabs';
import type { ParamMatcher } from '@sveltejs/kit';

/** One placeholder route serves every tab we have not built yet. */
export const match: ParamMatcher = (param) => USER_TAB_SLUGS.includes(param);
