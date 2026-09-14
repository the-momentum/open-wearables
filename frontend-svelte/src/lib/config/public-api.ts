import { env } from '$env/dynamic/public';

/** What a client dials, unlike the server's own API_URL. Empty when unset. */
export const publicApiUrl = (): string => env.VITE_API_URL ?? '';
