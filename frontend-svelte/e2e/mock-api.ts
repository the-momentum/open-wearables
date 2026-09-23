/**
 * Stand-in for FastAPI so end-to-end tests walk the real sign-in path without
 * the full stack. Started by playwright.config.ts. Mirrors the contracts in
 * backend/app/api/routes/v1/{auth,token}.py.
 */
import {
	CREDENTIALS,
	DEVELOPER,
	PROVIDER_SETTINGS,
	createApiKey,
	createApplication,
	createInvitation,
	deleteApiKey,
	deleteApplication,
	deleteDeveloper,
	listApiKeys,
	listApplications,
	listDevelopers,
	listDeviceTypePriorities,
	listInvitations,
	listProviderPriorities,
	renameApiKey,
	resetSettings,
	resetLifecycle,
	resetSeed,
	resetSyncs,
	syncScans,
	listGlobalRuns,
	storedRun,
	lastSeed,
	queueSeed,
	SEED_PRESETS,
	SLEEP_PROFILES,
	lifecycleScans,
	readLifecycle,
	saveLifecycle,
	revokeInvitation,
	rotateApiKey,
	rotateApplicationSecret,
	saveDeviceTypePriorities,
	saveProviderPriorities,
	setLiveSyncMode,
	liveSyncCalls,
	setProviderEnabled,
	makeConnections,
	createSubscription,
	deleteSubscription,
	listSubscriptions,
	makeCoverage,
	makeDeliveries,
	makeEventTypes,
	makeDataSummary,
	makeDataTimeline,
	makeRecentRuns,
	makeSyncHistory,
	makeSystemInfo,
	deleteCycle,
	deleteSleep,
	makeActivity,
	makeBody,
	deleteWorkout,
	makeCycles,
	makeScores,
	makeSleep,
	makeUsers,
	makeTimeseries,
	makeVitals,
	makeWorkouts,
	workoutTypes,
	resetActivity,
	resetCycles,
	resetWebhooks,
	updateSubscription,
	resetSleep,
	resetWorkouts
} from './fixtures';

// Mutable: the write endpoints change it, and /__reset restores it between tests.
let USERS = makeUsers();
/** Connections revoked during a test, so the detail endpoints agree with the list. */
let DISCONNECTED = new Set<string>();
/** Holds the workouts summary query back, so a test can watch the page stream. */
let SLOW_SUMMARY = false;
/** Lets a test see what an untouched archive looks like on the dashboard. */
let EMPTY_ARCHIVE = false;

const PORT = Number(process.env.MOCK_API_PORT ?? 8787);

let issued = 0;
const validAccessTokens = new Set<string>();
const validRefreshTokens = new Set<string>();

function issueTokens() {
	issued += 1;
	const access = `access-${issued}`;
	const refresh = `rt-${issued}`;
	validAccessTokens.add(access);
	validRefreshTokens.add(refresh);
	return { access_token: access, token_type: 'bearer', refresh_token: refresh, expires_in: 3600 };
}

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const server = Bun.serve({
	port: PORT,
	async fetch(request) {
		const { pathname } = new URL(request.url);

		if (pathname === '/__reset') {
			USERS = makeUsers();
			DISCONNECTED = new Set();
			SLOW_SUMMARY = false;
			EMPTY_ARCHIVE = false;
			resetWorkouts();
			resetSleep();
			resetActivity();
			resetCycles();
			resetWebhooks();
			resetSettings();
			resetLifecycle();
			resetSeed();
			resetSyncs();
			return new Response(null, { status: 204 });
		}

		if (pathname === '/__empty-archive') {
			EMPTY_ARCHIVE = true;
			return new Response(null, { status: 204 });
		}

		if (pathname === '/__slow-summary') {
			SLOW_SUMMARY = true;
			return new Response(null, { status: 204 });
		}

		if (pathname === '/api/v1/auth/login') {
			const form = await request.formData();
			const ok =
				form.get('username') === CREDENTIALS.email && form.get('password') === CREDENTIALS.password;
			return ok ? json(issueTokens()) : json({ detail: 'Incorrect email or password' }, 401);
		}

		if (pathname === '/api/v1/auth/me') {
			const token = request.headers.get('authorization')?.replace('Bearer ', '') ?? '';
			return validAccessTokens.has(token) ? json(DEVELOPER) : json({ detail: 'Unauthorized' }, 401);
		}

		const authorizeMatch = pathname.match(/^\/api\/v1\/oauth\/([^/]+)\/authorize$/);
		if (authorizeMatch) {
			const provider = authorizeMatch[1];
			if (provider === 'whoop') {
				return json({ detail: 'Provider credentials are not configured.' }, 400);
			}
			// A real provider sends the browser to redirect_uri once the person
			// consents, so handing it straight back walks the same path.
			const redirectUri = new URL(request.url).searchParams.get('redirect_uri') ?? '/';
			return json({ authorization_url: redirectUri, state: 'state-1' });
		}

		if (pathname === '/api/v1/webhooks/event-types') {
			return json(makeEventTypes());
		}

		const testMatch = pathname.match(/^\/api\/v1\/webhooks\/endpoints\/([^/]+)\/test$/);
		if (testMatch && request.method === 'POST') {
			const { event_type } = await request.json();
			// The real thing queues it, so a delivery does not appear at once.
			return json({ message: 'Test event sent successfully.', message_id: `msg_${event_type}` });
		}

		const attemptsMatch = pathname.match(/^\/api\/v1\/webhooks\/endpoints\/([^/]+)\/attempts$/);
		if (attemptsMatch) {
			return json(makeDeliveries(new URL(request.url).searchParams));
		}

		const endpointMatch = pathname.match(/^\/api\/v1\/webhooks\/endpoints\/([^/]+)$/);
		if (endpointMatch) {
			if (request.method === 'DELETE') {
				return deleteSubscription(endpointMatch[1])
					? new Response(null, { status: 204 })
					: json({ detail: 'Not found' }, 404);
			}
			if (request.method === 'PATCH') {
				const updated = updateSubscription(endpointMatch[1], await request.json());
				return updated ? json(updated) : json({ detail: 'Not found' }, 404);
			}
		}

		if (pathname === '/api/v1/webhooks/endpoints') {
			if (request.method === 'POST') {
				const body = await request.json();
				if (!String(body.url ?? '').startsWith('https://')) {
					return json({ detail: 'Webhook URL must use HTTPS' }, 422);
				}
				return json(createSubscription(body), 201);
			}
			return json(listSubscriptions());
		}

		if (pathname === '/api/v1/meta/coverage') {
			return json(makeCoverage());
		}

		if (pathname === '/api/v1/dashboard/stats') {
			const info = makeSystemInfo();
			if (EMPTY_ARCHIVE) info.data_points.archived = 0;
			return json(info);
		}

		if (pathname === '/api/v1/oauth/providers') {
			if (request.method === 'PUT') {
				const { providers } = await request.json();
				return json(setProviderEnabled(providers));
			}
			return json(PROVIDER_SETTINGS);
		}

		const liveSyncMatch = pathname.match(/^\/api\/v1\/oauth\/providers\/([^/]+)$/);
		if (liveSyncMatch && request.method === 'PUT') {
			const { live_sync_mode } = await request.json();
			const updated = setLiveSyncMode(liveSyncMatch[1], live_sync_mode);
			return updated ? json(updated) : json({ detail: 'Not found' }, 404);
		}

		// ------------------------------------------------------------ settings --

		if (pathname === '/__sync-scans') {
			return json({ scans: syncScans() });
		}

		if (pathname === '/api/v1/sync/runs') {
			return json(listGlobalRuns(new URL(request.url).searchParams));
		}

		const storedMatch = pathname.match(/^\/api\/v1\/sync\/history\/([^/]+)$/);
		if (storedMatch) {
			const stored = storedRun(decodeURIComponent(storedMatch[1]));
			return stored ? json(stored) : json({ detail: 'Sync run not found' }, 404);
		}

		if (pathname === '/__live-sync-calls') {
			return json({ calls: liveSyncCalls() });
		}

		if (pathname === '/__last-seed') {
			return json({ request: lastSeed() });
		}

		if (pathname === '/api/v1/settings/seed/presets') return json(SEED_PRESETS);
		if (pathname === '/api/v1/settings/seed/sleep-profiles') return json(SLEEP_PROFILES);

		if (pathname === '/api/v1/settings/seed' && request.method === 'POST') {
			const body = await request.json();
			if (body.num_users < 1 || body.num_users > 10) {
				return json({ detail: [{ loc: ['body', 'num_users'], msg: 'out of range' }] }, 422);
			}
			return json(queueSeed(body), 202);
		}

		if (pathname === '/__lifecycle-scans') {
			return json({ scans: lifecycleScans() });
		}

		if (pathname === '/api/v1/settings/archival/run' && request.method === 'POST') {
			return json({ task_id: 'task-1', status: 'dispatched' }, 202);
		}

		if (pathname === '/api/v1/settings/archival') {
			if (request.method === 'PUT') {
				const body = await request.json();
				const out = (days: unknown, max: number) =>
					days !== null &&
					(!Number.isInteger(days) || (days as number) < 1 || (days as number) > max);
				if (out(body.archive_after_days, 3650) || out(body.delete_after_days, 7300)) {
					// FastAPI's shape: a list, no string `detail` to show.
					return json({ detail: [{ loc: ['body'], msg: 'out of range' }] }, 422);
				}
				return json(saveLifecycle(body));
			}
			return json(readLifecycle());
		}

		const keyMatch = pathname.match(/^\/api\/v1\/developer\/api-keys\/([^/]+)(\/rotate)?$/);
		if (keyMatch) {
			const [, id, rotating] = keyMatch;
			if (rotating && request.method === 'POST') {
				const rotated = rotateApiKey(id);
				return rotated ? json(rotated) : json({ detail: 'Not found' }, 404);
			}
			if (request.method === 'PATCH') {
				const { name } = await request.json();
				const renamed = renameApiKey(id, name);
				return renamed ? json(renamed) : json({ detail: 'Not found' }, 404);
			}
			if (request.method === 'DELETE') {
				return deleteApiKey(id)
					? new Response(null, { status: 204 })
					: json({ detail: 'Not found' }, 404);
			}
		}

		if (pathname === '/api/v1/developer/api-keys') {
			if (request.method === 'POST') {
				const { name } = await request.json();
				if (!String(name ?? '').trim()) return json({ detail: 'Name is required' }, 422);
				return json(createApiKey(name), 201);
			}
			return json(listApiKeys());
		}

		const appMatch = pathname.match(/^\/api\/v1\/applications\/([^/]+)(\/rotate-secret)?$/);
		if (appMatch) {
			const [, appId, rotating] = appMatch;
			if (rotating && request.method === 'POST') {
				const rotated = rotateApplicationSecret(appId);
				return rotated ? json(rotated) : json({ detail: 'Not found' }, 404);
			}
			if (request.method === 'DELETE') {
				return deleteApplication(appId)
					? new Response(null, { status: 204 })
					: json({ detail: 'Not found' }, 404);
			}
		}

		if (pathname === '/api/v1/applications') {
			if (request.method === 'POST') {
				const { name } = await request.json();
				return json(createApplication(name), 201);
			}
			return json(listApplications());
		}

		if (pathname === '/api/v1/priorities/providers') {
			if (request.method === 'PUT') {
				const { priorities } = await request.json();
				return json(saveProviderPriorities(priorities));
			}
			return json(listProviderPriorities());
		}

		if (pathname === '/api/v1/priorities/device-types') {
			if (request.method === 'PUT') {
				const { priorities } = await request.json();
				return json(saveDeviceTypePriorities(priorities));
			}
			return json(listDeviceTypePriorities());
		}

		if (pathname === '/api/v1/developers') {
			return json(listDevelopers());
		}

		const developerMatch = pathname.match(/^\/api\/v1\/developers\/([^/]+)$/);
		if (developerMatch && request.method === 'DELETE') {
			return deleteDeveloper(developerMatch[1])
				? new Response(null, { status: 204 })
				: json({ detail: 'Not found' }, 404);
		}

		const invitationMatch = pathname.match(/^\/api\/v1\/invitations\/([^/]+)(\/resend)?$/);
		if (invitationMatch) {
			const [, id, resending] = invitationMatch;
			if (resending && request.method === 'POST') return json({ message: 'Invitation resent.' });
			if (request.method === 'DELETE') {
				return revokeInvitation(id)
					? new Response(null, { status: 204 })
					: json({ detail: 'Not found' }, 404);
			}
		}

		if (pathname === '/api/v1/invitations') {
			if (request.method === 'POST') {
				const { email } = await request.json();
				if (listDevelopers().some((developer) => developer.email === email)) {
					return json({ detail: 'That person is already on the team.' }, 409);
				}
				return json(createInvitation(email), 201);
			}
			return json(listInvitations());
		}

		if (pathname === '/api/v1/auth/change-password' && request.method === 'POST') {
			const { current_password } = await request.json();
			return current_password === CREDENTIALS.password
				? json({ message: 'Password updated successfully.' })
				: json({ detail: 'Incorrect current password' }, 400);
		}

		if (pathname === '/api/v1/users' && request.method === 'POST') {
			const body = await request.json();
			if (USERS.some((user) => body.email && user.email === body.email)) {
				return json({ detail: 'User with this email already exists.' }, 409);
			}
			const created = {
				id: `00000000-0000-4000-8000-${String(USERS.length + 1).padStart(12, '0')}`,
				created_at: new Date().toISOString(),
				first_name: body.first_name ?? null,
				last_name: body.last_name ?? null,
				email: body.email ?? null,
				external_user_id: body.external_user_id ?? null,
				last_synced_at: null,
				last_synced_provider: null,
				has_active_connection: false,
				connections: []
			};
			USERS.unshift(created);
			return json(created, 201);
		}

		const inviteMatch = pathname.match(/^\/api\/v1\/users\/([^/]+)\/invitation-code$/);
		if (inviteMatch && request.method === 'POST') {
			return json(
				{
					id: 'invite-1',
					code: 'ABCD-1234',
					user_id: inviteMatch[1],
					expires_at: '2026-09-09T12:00:00Z',
					created_at: '2026-09-08T12:00:00Z'
				},
				201
			);
		}

		const connectionMatch = pathname.match(
			/^\/api\/v1\/users\/([^/]+)\/connections\/([^/]+)(\/data)?$/
		);
		if (connectionMatch && request.method === 'DELETE') {
			const user = USERS.find((candidate) => candidate.id === connectionMatch[1]);
			if (!user) return json({ detail: 'User not found' }, 404);
			// Both revoke and purge end the connection, which is what the UI reads.
			user.connections = user.connections.filter((c) => c.provider !== connectionMatch[2]);
			DISCONNECTED.add(`${connectionMatch[1]}:${connectionMatch[2]}`);
			return new Response(null, { status: 204 });
		}

		const syncMatch = pathname.match(
			/^\/api\/v1\/providers\/([^/]+)\/users\/([^/]+)\/sync(\/historical)?$/
		);
		if (syncMatch && request.method === 'POST') {
			return json({ status: 'queued', provider: syncMatch[1] });
		}

		const eventMatch = pathname.match(
			/^\/api\/v1\/users\/([^/]+)\/events\/(workouts|sleep|menstrual-cycles)\/([^/]+)$/
		);
		if (eventMatch && request.method === 'DELETE') {
			const remove = {
				workouts: deleteWorkout,
				sleep: deleteSleep,
				'menstrual-cycles': deleteCycle
			}[eventMatch[2]]!;
			return remove(eventMatch[3])
				? new Response(null, { status: 204 })
				: json({ detail: 'Not found' }, 404);
		}

		const detailMatch = pathname.match(/^\/api\/v1\/users\/([^/]+)(\/.+)?$/);
		if (detailMatch && request.method === 'GET') {
			const user = USERS.find((candidate) => candidate.id === detailMatch[1]);
			if (!user) return json({ detail: 'User not found' }, 404);

			const connected = user.connections.length > 0;
			switch (detailMatch[2]) {
				case undefined: {
					// The backend derives these from the connections, so the mock must
					// too — otherwise the header contradicts the provider cards.
					const latest = connected ? makeConnections(user.id)[0] : null;
					return json({
						...user,
						last_synced_at: latest?.last_synced_at ?? null,
						last_synced_provider: latest?.provider ?? null,
						has_active_connection: connected,
						connections: null,
						// Only one user gates the tab on, so a test can assert both cases.
						has_womens_health_data: user.first_name === 'Zofia'
					});
				}
				case '/connections':
					return json(
						connected
							? makeConnections(user.id).filter(
									(c) => !DISCONNECTED.has(`${user.id}:${c.provider}`)
								)
							: []
					);
				case '/sync/history':
					return json(connected ? makeSyncHistory(user.id) : []);
				case '/summaries/data':
					return json(makeDataSummary());
				case '/summaries/data/timeline': {
					const query = new URL(request.url).searchParams;
					return json(
						makeDataTimeline(
							query.get('bucket') ?? 'day',
							query.get('group_by') ?? 'provider',
							query.get('provider') ?? ''
						)
					);
				}
				case '/summaries/body':
					return json(connected ? makeBody() : null);
				case '/timeseries': {
					const query = new URL(request.url).searchParams;
					// The body tab asks for vitals; every other caller asks for a
					// session's own sensors.
					return json(
						query.getAll('types').includes('resting_heart_rate')
							? makeVitals(query)
							: makeTimeseries(query)
					);
				}
				case '/events/workouts/types':
					return json(workoutTypes());
				case '/events/workouts': {
					const query = new URL(request.url).searchParams;
					// The page asks for one screen of records and, separately, for
					// everything in the period to sum. Only the second is held back.
					if (SLOW_SUMMARY && Number(query.get('limit')) > 100) {
						await new Promise((resolve) => setTimeout(resolve, 600));
					}
					return json(makeWorkouts(query));
				}
				case '/summaries/activity':
					return json(makeActivity(new URL(request.url).searchParams));
				case '/health-scores':
					// Gated like the other data endpoints: a user with no connection has
					// nothing scored, which is the empty state worth testing.
					return json(
						connected
							? makeScores(new URL(request.url).searchParams)
							: { data: [], pagination: { total_count: 0, has_more: false } }
					);
				case '/events/menstrual-cycles':
					// Gated like the other data endpoints, and only for the user the
					// detail route marks as having this data.
					return json(
						user.first_name === 'Zofia'
							? makeCycles(new URL(request.url).searchParams)
							: { data: [], pagination: { has_more: false, total_count: 0 } }
					);
				case '/events/sleep':
					return json(makeSleep(new URL(request.url).searchParams));
				case '/sync/runs':
					return json(connected ? makeRecentRuns(user.id) : []);
				default:
					return json({ detail: 'Not found' }, 404);
			}
		}

		const userMatch = pathname.match(/^\/api\/v1\/users\/([^/]+)$/);
		if (userMatch && request.method !== 'GET') {
			const index = USERS.findIndex((user) => user.id === userMatch[1]);
			if (index === -1) return json({ detail: 'Not found' }, 404);

			if (request.method === 'DELETE') return json(USERS.splice(index, 1)[0]);

			const body = await request.json();
			if (body.email && USERS.some((user, i) => i !== index && user.email === body.email)) {
				return json({ detail: 'User with this email already exists.' }, 409);
			}
			Object.assign(USERS[index], {
				first_name: body.first_name ?? null,
				last_name: body.last_name ?? null,
				email: body.email ?? null,
				external_user_id: body.external_user_id ?? null
			});
			return json(USERS[index]);
		}

		if (pathname === '/api/v1/users') {
			const params = new URL(request.url).searchParams;
			const search = params.get('search')?.toLowerCase() ?? '';
			const page = Number(params.get('page') ?? 1);
			const limit = Number(params.get('limit') ?? 20);
			const includeConnections = params.getAll('include').includes('connections');

			const wantedProviders = params.getAll('provider');

			let matched = USERS.filter((user) => {
				if (
					search &&
					![user.first_name, user.last_name, user.email, user.id]
						.join(' ')
						.toLowerCase()
						.includes(search)
				) {
					return false;
				}
				if (
					wantedProviders.length > 0 &&
					!user.connections.some((c) => wantedProviders.includes(c.provider))
				) {
					return false;
				}
				return true;
			});

			const direction = params.get('sort_order') === 'asc' ? 1 : -1;
			const key = params.get('sort_by') ?? 'created_at';
			matched = [...matched].sort((a, b) => {
				const left = key === 'name' ? `${a.first_name} ${a.last_name}` : String(a[key] ?? '');
				const right = key === 'name' ? `${b.first_name} ${b.last_name}` : String(b[key] ?? '');
				return left.localeCompare(right) * direction;
			});

			const items = matched.slice((page - 1) * limit, page * limit).map((user) => ({
				...user,
				connections: includeConnections ? user.connections : null
			}));

			return json({
				items,
				total: matched.length,
				page,
				limit,
				pages: Math.ceil(matched.length / limit),
				has_next: page * limit < matched.length,
				has_prev: page > 1
			});
		}

		if (pathname === '/api/v1/token/refresh') {
			const { refresh_token } = await request.json();
			if (!validRefreshTokens.has(refresh_token)) return json({ detail: 'Invalid' }, 401);
			// The real backend rotates: the old token stops working.
			validRefreshTokens.delete(refresh_token);
			return json(issueTokens());
		}

		if (pathname === '/api/v1/token/revoke') {
			const { refresh_token } = await request.json();
			validRefreshTokens.delete(refresh_token);
			return new Response(null, { status: 204 });
		}

		return json({ detail: 'Not found' }, 404);
	}
});

console.log(`mock api listening on ${server.url}`);
