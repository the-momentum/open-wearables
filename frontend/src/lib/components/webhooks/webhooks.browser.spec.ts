import { page } from 'vitest/browser';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SigningSecret from './SigningSecret.svelte';

const KEY = 'whsec_C2FVsBQIhrscChlQIMV+b5ND9vAIBZaM7ZqtLnNYGDA=';

function stubSecret(response: () => Response) {
	const fetchMock = vi.fn(async () => response());
	vi.stubGlobal('fetch', fetchMock);
	return fetchMock;
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('SigningSecret', () => {
	it('starts masked and does not ask for the secret until someone does', async () => {
		const fetchMock = stubSecret(() => Response.json({ key: KEY }));
		await render(SigningSecret, { id: 'ep_1' });

		await expect.element(page.getByLabelText('Signing secret, hidden')).toBeVisible();
		await expect.element(page.getByText(KEY)).not.toBeInTheDocument();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('reveals the secret on demand and hides it again', async () => {
		const fetchMock = stubSecret(() => Response.json({ key: KEY }));
		await render(SigningSecret, { id: 'ep_1' });

		await page.getByRole('button', { name: 'Reveal' }).click();
		await expect.element(page.getByText(KEY)).toBeVisible();
		expect(fetchMock).toHaveBeenCalledWith('/webhooks/ep_1/secret', { cache: 'no-store' });

		await page.getByRole('button', { name: 'Hide' }).click();
		await expect.element(page.getByText(KEY)).not.toBeInTheDocument();

		// Shown again from what it already has, without a second request.
		await page.getByRole('button', { name: 'Reveal' }).click();
		await expect.element(page.getByText(KEY)).toBeVisible();
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('says so when the secret cannot be loaded, and stays masked', async () => {
		stubSecret(() => new Response(null, { status: 502 }));
		await render(SigningSecret, { id: 'ep_1' });

		await page.getByRole('button', { name: 'Reveal' }).click();
		await expect.element(page.getByText(/Could not load the signing secret/)).toBeVisible();
		await expect.element(page.getByLabelText('Signing secret, hidden')).toBeVisible();
	});
});
