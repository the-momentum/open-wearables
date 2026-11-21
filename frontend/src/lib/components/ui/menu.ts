import { buttonClass } from './button';

/**
 * Menu entries are whole buttons, stacked on a phone and side by side from sm up.
 * Shared by entries that are buttons and by those that submit a form.
 */
export const menuItemClass = (destructive = false) =>
	buttonClass(destructive ? 'danger' : 'outline', 'md', 'w-full sm:flex-1');
