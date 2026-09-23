import KeyRound from '@lucide/svelte/icons/key-round';
import Plug from '@lucide/svelte/icons/plug';
import ArrowDownUp from '@lucide/svelte/icons/arrow-down-up';
import Archive from '@lucide/svelte/icons/archive';
import Users from '@lucide/svelte/icons/users';
import Sprout from '@lucide/svelte/icons/sprout';
import type { Component } from 'svelte';
import { resolve } from '$app/paths';

export type SettingsTab = {
	href: string;
	label: string;
	icon: Component;
	/** Marks a tab whose API is still moving under it. */
	beta?: boolean;
};

/**
 * Each tab is a route of its own, so a tab loads only what it shows — the old
 * dashboard mounted all seven at once and fetched for every one of them.
 * Written out rather than built from slugs: `resolve` checks the routes exist.
 */
export const SETTINGS_TABS: readonly SettingsTab[] = [
	{ href: resolve('/settings'), label: 'Credentials', icon: KeyRound },
	{ href: resolve('/settings/providers'), label: 'Providers', icon: Plug },
	{ href: resolve('/settings/priorities'), label: 'Priorities', icon: ArrowDownUp },
	{ href: resolve('/settings/data-lifecycle'), label: 'Data Lifecycle', icon: Archive, beta: true },
	{ href: resolve('/settings/team'), label: 'Team', icon: Users },
	{ href: resolve('/settings/seed-data'), label: 'Seed Data', icon: Sprout }
];

/** The href of the tab a path belongs to, so the strip can mark it. */
export function activeSettingsTab(pathname: string): string {
	const match = SETTINGS_TABS.find((tab) => tab.href === pathname);
	return match?.href ?? SETTINGS_TABS[0].href;
}
