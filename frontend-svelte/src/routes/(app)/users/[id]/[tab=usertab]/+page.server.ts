import { userActions } from '$lib/server/user-actions';
import type { Actions } from './$types';

/** The header lives in the layout, so its actions must exist on every tab. */
export const actions = userActions as Actions;
