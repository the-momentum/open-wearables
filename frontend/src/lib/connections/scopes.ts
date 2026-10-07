/** One string, in three shapes: space separated, comma separated, or URLs. */
export function parseScopes(scope: string | null): string[] {
	return (scope ?? '')
		.split(/[\s,]+/)
		.map((entry) => entry.trim())
		.filter(Boolean);
}

/** A scope URL carries its meaning in the last path segment; keep only that. */
export function scopeLabel(scope: string): string {
	if (!/^https?:\/\//.test(scope)) return scope;

	const segment = scope.replace(/\/+$/, '').split('/').pop();
	return segment || scope;
}
