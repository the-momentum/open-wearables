import { apiGet, apiPost, apiPut } from './api';
import { keep, recall } from './cache';
import type { ArchivalSettings, Lifecycle } from '$lib/lifecycle/types';

const PATH = '/api/v1/settings/archival';
const KEY = 'ow:lifecycle';
const TTL_SECONDS = 60;

/**
 * Both the GET and the PUT scan the whole of `data_point_series` for its date
 * span — the one index carrying `recorded_at` has it third, so MIN/MAX cannot
 * use it. A minute's cache keeps that to one pass however often the tab opens.
 */
export const cachedLifecycle = () => recall<Lifecycle>(KEY);

export const fetchLifecycle = async (accessToken: string) =>
	keep(KEY, await apiGet<Lifecycle>(PATH, accessToken), TTL_SECONDS);

/** The PUT answers with fresh sizes too, so the reload after a save is a hit. */
export const saveLifecycle = async (settings: ArchivalSettings, accessToken: string) =>
	keep(KEY, await apiPut<Lifecycle>(PATH, accessToken, settings), TTL_SECONDS);

export const runLifecycle = (accessToken: string) =>
	apiPost<{ task_id: string; status: string }>(`${PATH}/run`, accessToken);
