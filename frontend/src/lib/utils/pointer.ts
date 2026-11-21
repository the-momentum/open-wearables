import { MediaQuery } from 'svelte/reactivity';

/**
 * A mouse or a trackpad, where the app draws its own pickers; touch keeps the
 * system's. False on the server, so the first paint is the native control.
 */
export const finePointer = new MediaQuery('(pointer: fine)', false);
