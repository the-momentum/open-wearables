/** Mirrors backend `DataSourceResponse`: one device or app a user's data came from. */
export type DataSource = {
	id: string;
	provider: string;
	device_model: string | null;
	/** Marketing name for a raw model code (Watch6,2), else the model itself. Absent from older APIs. */
	device_name?: string | null;
	device_type: string | null;
	/** What the provider calls the source: a device or app name, an app id, or its own slug. */
	source: string | null;
	software_version: string | null;
};

export type SourceGroup = { provider: string; sources: DataSource[] };
