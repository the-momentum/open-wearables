import Armchair from '@lucide/svelte/icons/armchair';
import Moon from '@lucide/svelte/icons/moon';
import type { Component } from 'svelte';
import type { SleepSession } from './types';

/** What the card is called: the distinction an admin scans the list for. */
export const sleepKind = (session: SleepSession) => (session.is_nap ? 'Nap' : 'Night sleep');

/** A nap is daytime sleep in a chair, not a night — the mark should say so. */
export const sleepIcon = (session: SleepSession): Component => (session.is_nap ? Armchair : Moon);
