import { apiGet, apiPost } from './api';
import type { SeedPreset, SeedRequest, SeedResponse, SleepProfile } from '$lib/seed/types';

const PATH = '/api/v1/settings/seed';

export const listPresets = (accessToken: string) =>
	apiGet<SeedPreset[]>(`${PATH}/presets`, accessToken);

export const listSleepProfiles = (accessToken: string) =>
	apiGet<SleepProfile[]>(`${PATH}/sleep-profiles`, accessToken);

/** Queued, not run: the answer carries the task and the seed it will use. */
export const generateSeed = (request: SeedRequest, accessToken: string) =>
	apiPost<SeedResponse>(PATH, accessToken, request);
