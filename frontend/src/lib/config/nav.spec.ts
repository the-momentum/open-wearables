import { describe, expect, it } from 'vitest';
import { NAV_ITEMS, PRIMARY_NAV_ITEMS, isNavItemActive, type NavItem } from './nav';

const users = NAV_ITEMS.find((item) => item.href === '/users') as NavItem;
const docs = NAV_ITEMS.find((item) => item.external) as NavItem;

describe('isNavItemActive', () => {
	it('matches the exact path', () => {
		expect(isNavItemActive(users, '/users')).toBe(true);
	});

	it('matches a nested path so a detail page keeps its parent highlighted', () => {
		expect(isNavItemActive(users, '/users/abc-123')).toBe(true);
	});

	it('does not match a path that merely shares a prefix', () => {
		expect(isNavItemActive(users, '/users-export')).toBe(false);
	});

	it('never marks an external link active', () => {
		expect(isNavItemActive(docs, docs.href)).toBe(false);
	});
});

describe('NAV_ITEMS', () => {
	it('keeps at most four primary items, leaving the fifth bottom-bar slot for More', () => {
		expect(PRIMARY_NAV_ITEMS.length).toBeLessThanOrEqual(4);
	});
});
