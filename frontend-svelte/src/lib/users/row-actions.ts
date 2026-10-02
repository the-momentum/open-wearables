import { getContext, setContext } from 'svelte';
import type { User } from './types';

export type RowActions = {
	edit(user: User): void;
	remove(user: User): void;
};

/**
 * The dialogs live once at page level, not once per row. This carries the
 * openers down to `UserActions` without threading props through the list, the
 * table and the card.
 */
const KEY = Symbol('user-row-actions');

export const setRowActions = (actions: RowActions) => setContext(KEY, actions);
export const getRowActions = () => getContext<RowActions>(KEY);
