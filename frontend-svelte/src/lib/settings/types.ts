/** Mirrors backend `ApiKeyRead`. The secret itself never comes back. */
export type ApiKey = {
	id: string;
	name: string;
	key_prefix: string;
	created_at: string;
};

/** `ApiKeyReadWithSecret` — the one response that carries the key. */
export type ApiKeySecret = ApiKey & { key: string };

/** Mirrors `ApplicationRead`: SDK credentials for a mobile app. */
export type Application = {
	id: string;
	app_id: string;
	name: string;
	created_at: string;
};

export type ApplicationSecret = Application & { app_secret: string };

/** Mirrors `ProviderSettingRead`. */
export type ProviderSetting = {
	provider: string;
	name: string;
	has_cloud_api: boolean;
	is_enabled: boolean;
	icon_url: string;
	live_sync_mode: 'pull' | 'webhook' | null;
	live_sync_configurable: boolean;
};

/** Both priority lists have the same shape under a different key. */
export type ProviderPriority = { provider: string; priority: number };
export type DeviceTypePriority = { device_type: string; priority: number };

/** Mirrors `DeveloperRead`. */
export type Developer = {
	id: string;
	email: string;
	first_name: string | null;
	last_name: string | null;
	created_at: string;
};

export type InvitationStatus = 'pending' | 'sent' | 'failed' | 'accepted' | 'expired' | 'revoked';

/** Mirrors `InvitationRead`. The token is what the invite link carries. */
export type Invitation = {
	id: string;
	email: string;
	token: string;
	status: InvitationStatus;
	expires_at: string;
	created_at: string;
};
