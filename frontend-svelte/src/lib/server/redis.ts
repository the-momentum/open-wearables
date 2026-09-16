import Redis from 'ioredis';
import { env } from '$env/dynamic/private';

const DEFAULT_REDIS_URL = 'redis://localhost:6379/2';

let client: Redis | undefined;

/**
 * Not Bun's built-in client: the Vite binary has a `#!/usr/bin/env node`
 * shebang, so dev, preview and build run this under node. Lazy so importing
 * never opens a connection.
 */
export function redis(): Redis {
	if (!client) {
		client = new Redis(env.REDIS_URL || DEFAULT_REDIS_URL, { maxRetriesPerRequest: 2 });
		// An 'error' with no listener is fatal in node.
		client.on('error', (error: Error) => console.error('[redis]', error.message));
	}
	return client;
}
