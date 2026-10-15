import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import House from '@lucide/svelte/icons/house';
import NavLink from './NavLink.svelte';
import type { NavItem } from '$lib/config/nav';

const internal: NavItem = { label: 'Dashboard', href: '/dashboard', icon: House, primary: true };

const external: NavItem = {
	label: 'Documentation',
	href: 'https://openwearables.io/docs',
	icon: House,
	primary: false,
	external: true
};

describe('NavLink', () => {
	it('marks the active destination for assistive tech, not only with colour', async () => {
		render(NavLink, { item: internal, active: true });

		await expect
			.element(page.getByRole('link', { name: 'Dashboard' }))
			.toHaveAttribute('aria-current', 'page');
	});

	it('opens an external destination in a new tab without leaking the referrer', async () => {
		render(NavLink, { item: external });

		const link = page.getByRole('link', { name: /Documentation/ });
		await expect.element(link).toHaveAttribute('target', '_blank');
		await expect.element(link).toHaveAttribute('rel', 'noreferrer');
	});
});
