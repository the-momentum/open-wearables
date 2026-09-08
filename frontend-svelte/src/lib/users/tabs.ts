import Activity from '@lucide/svelte/icons/activity';
import ChartColumn from '@lucide/svelte/icons/chart-column';
import Dumbbell from '@lucide/svelte/icons/dumbbell';
import Heart from '@lucide/svelte/icons/heart';
import Moon from '@lucide/svelte/icons/moon';
import Scale from '@lucide/svelte/icons/scale';
import Trophy from '@lucide/svelte/icons/trophy';
import Plug from '@lucide/svelte/icons/plug';
import type { Component } from 'svelte';
import { resolve } from '$app/paths';
import type { UserDetail } from './types';

export type UserTab = {
	/** Path segment under /users/{id}; empty for the index tab. */
	slug: string;
	label: string;
	icon: Component;
	/** Hidden unless the user actually has this kind of data. */
	gated?: boolean;
};

export const USER_TABS: readonly UserTab[] = [
	// Not "Profile": the profile is the header, visible above every tab.
	{ slug: '', label: 'Connections', icon: Plug },
	{ slug: 'data', label: 'Data Summary', icon: ChartColumn },
	{ slug: 'workouts', label: 'Workouts', icon: Dumbbell },
	{ slug: 'activity', label: 'Activity', icon: Activity },
	{ slug: 'sleep', label: 'Sleep', icon: Moon },
	{ slug: 'body', label: 'Body', icon: Scale },
	{ slug: 'scores', label: 'Scores', icon: Trophy },
	{ slug: 'womens-health', label: "Women's Health", icon: Heart, gated: true }
];

/** What the route matcher accepts, so an invented tab 404s. */
export const USER_TAB_SLUGS = USER_TABS.map((tab) => tab.slug).filter(Boolean);

export function tabsFor(user: Pick<UserDetail, 'has_womens_health_data'>): UserTab[] {
	return USER_TABS.filter((tab) => !tab.gated || user.has_womens_health_data);
}

export function tabLabel(slug: string): string {
	return USER_TABS.find((tab) => tab.slug === slug)?.label ?? slug;
}

export const userTabHref = (userId: string, slug: string) =>
	slug ? resolve(`/users/${userId}/${slug}`) : resolve(`/users/${userId}`);

export function activeTabSlug(pathname: string, userId: string): string {
	const base = resolve(`/users/${userId}`);
	return pathname === base ? '' : pathname.slice(base.length + 1);
}
