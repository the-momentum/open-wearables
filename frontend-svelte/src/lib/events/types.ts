/**
 * Mirrors backend `SourceMetadata`, which every event response carries — a
 * workout, a night, a day, a cycle. `provider` is the integration, `source` the
 * writer inside it.
 */
export type SourceMetadata = {
	provider: string;
	source: string | null;
	device: string | null;
	device_type: string | null;
	device_name: string | null;
};
