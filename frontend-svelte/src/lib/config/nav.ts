import type { Component } from 'svelte';
import { resolve } from '$app/paths';
import type { LucideProps } from '@lucide/svelte';
import House from '@lucide/svelte/icons/house';
import Users from '@lucide/svelte/icons/users';
import RefreshCw from '@lucide/svelte/icons/refresh-cw';
import Webhook from '@lucide/svelte/icons/webhook';
import LayoutGrid from '@lucide/svelte/icons/layout-grid';
import Settings from '@lucide/svelte/icons/settings';
import FileText from '@lucide/svelte/icons/file-text';

export type NavItem = {
	label: string;
	href: string;
	icon: Component<LucideProps>;
	/** Shown directly in the mobile bottom bar; the rest live behind "More". */
	primary: boolean;
	external?: boolean;
};

/**
 * The one place navigation is defined; sidebar, bottom bar and More sheet all
 * derive from it. At most four `primary` items — the fifth bottom-bar slot is
 * "More", and a unit test enforces it.
 */
export const NAV_ITEMS: NavItem[] = [
	{ label: 'Dashboard', href: resolve('/dashboard'), icon: House, primary: true },
	{ label: 'Users', href: resolve('/users'), icon: Users, primary: true },
	{ label: 'Syncs', href: resolve('/syncs'), icon: RefreshCw, primary: true },
	{ label: 'Webhooks', href: resolve('/webhooks'), icon: Webhook, primary: true },
	{ label: 'Data Coverage', href: resolve('/coverage'), icon: LayoutGrid, primary: false },
	{ label: 'Settings', href: resolve('/settings'), icon: Settings, primary: false },
	{
		label: 'Documentation',
		href: 'https://openwearables.io/docs',
		icon: FileText,
		primary: false,
		external: true
	}
];

export const PRIMARY_NAV_ITEMS = NAV_ITEMS.filter((item) => item.primary);
export const SECONDARY_NAV_ITEMS = NAV_ITEMS.filter((item) => !item.primary);

/** Nested paths count, so `/users/abc-123` still highlights "Users". */
export function isNavItemActive(item: NavItem, pathname: string): boolean {
	if (item.external) return false;
	return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

/** Label of the destination a path belongs to — drives the header and <title>. */
export function navLabelFor(pathname: string): string | undefined {
	return NAV_ITEMS.find((item) => isNavItemActive(item, pathname))?.label;
}
