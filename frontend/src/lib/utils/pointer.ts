import { MediaQuery } from 'svelte/reactivity';

/**
 * A mouse or a trackpad: where the app draws its own pickers. A touch screen
 * keeps the system's, which its users know and which suits a thumb. False on
 * the server, so the first paint is the native control and works unhydrated.
 */
export const finePointer = new MediaQuery('(pointer: fine)', false);
