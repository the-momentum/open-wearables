import { buttonClass } from './button';

/**
 * The design draws a menu's entries as whole buttons, stacked on a phone and side by
 * side in the desktop dialog. Shared by entries that are buttons and by those that
 * submit a form.
 */
export const menuItemClass = (destructive = false) =>
	buttonClass(destructive ? 'danger' : 'outline', 'md', 'w-full sm:flex-1');
