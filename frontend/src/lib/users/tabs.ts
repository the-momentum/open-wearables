import Activity from '@lucide/svelte/icons/activity';
import ChartColumn from '@lucide/svelte/icons/chart-column';
import Dumbbell from '@lucide/svelte/icons/dumbbell';
import Heart from '@lucide/svelte/icons/heart';
import MonitorSmartphone from '@lucide/svelte/icons/monitor-smartphone';
import Moon from '@lucide/svelte/icons/moon';
import Scale from '@lucide/svelte/icons/scale';
import Trophy from '@lucide/svelte/icons/trophy';
import Utensils from '@lucide/svelte/icons/utensils';
import Plug from '@lucide/svelte/icons/plug';
import type { Component } from 'svelte';
import { resolve } from '$app/paths';

export type UserTab = {
	/** Path segment under /users/{id}; empty for the index tab. */
	slug: string;
	label: string;
	icon: Component;
};

export const USER_TABS: readonly UserTab[] = [
	// Not "Profile": the profile is the header, visible above every tab.
	{ slug: '', label: 'Connections', icon: Plug },
	{ slug: 'data', label: 'Data Summary', icon: ChartColumn },
	{ slug: 'sources', label: 'Sources', icon: MonitorSmartphone },
	{ slug: 'workouts', label: 'Workouts', icon: Dumbbell },
	{ slug: 'activity', label: 'Activity', icon: Activity },
	{ slug: 'sleep', label: 'Sleep', icon: Moon },
	{ slug: 'meals', label: 'Meals', icon: Utensils },
	{ slug: 'body', label: 'Body', icon: Scale },
	{ slug: 'scores', label: 'Scores', icon: Trophy },
	{ slug: 'womens-health', label: "Women's Health", icon: Heart }
];

export function tabLabel(slug: string): string {
	return USER_TABS.find((tab) => tab.slug === slug)?.label ?? slug;
}

export const userTabHref = (userId: string, slug: string) =>
	slug ? resolve(`/users/${userId}/${slug}`) : resolve(`/users/${userId}`);

export function activeTabSlug(pathname: string, userId: string): string {
	const base = resolve(`/users/${userId}`);
	return pathname === base ? '' : pathname.slice(base.length + 1);
}
