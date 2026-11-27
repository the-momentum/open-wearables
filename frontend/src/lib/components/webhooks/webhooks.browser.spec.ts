import { page } from 'vitest/browser';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SigningSecret from './SigningSecret.svelte';

const KEY = 'whsec_C2FVsBQIhrscChlQIMV+b5ND9vAIBZaM7ZqtLnNYGDA=';

function stubSecret(response: () => Response | Promise<Response>) {
	const fetchMock = vi.fn(async () => response());
	vi.stubGlobal('fetch', fetchMock);
	return fetchMock;
}

/**
 * Stands in for the clipboard and, like the real one, waits for the item's text:
 * a pending text that rejects makes the write reject too.
 */
function stubClipboard() {
	const written: string[] = [];
	const clipboard = {
		write: vi.fn(async (items: ClipboardItem[]) => {
			written.push(await (await items[0].getType('text/plain')).text());
		}),
		writeText: vi.fn(async (text: string) => {
			written.push(text);
		})
	};
	vi.spyOn(navigator, 'clipboard', 'get').mockReturnValue(clipboard as unknown as Clipboard);
	return { clipboard, written };
}

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
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

	it('copies before revealing, keeps the field masked, and reuses that one request', async () => {
		let answer: (response: Response) => void = () => {};
		const fetchMock = stubSecret(() => new Promise<Response>((resolve) => (answer = resolve)));
		const { written } = stubClipboard();
		await render(SigningSecret, { id: 'ep_1' });

		await page.getByRole('button', { name: 'Copy signing secret' }).click();
		// The secret is still on its way: nothing is on the clipboard and nothing says so yet.
		await expect.element(page.getByRole('button', { name: 'Copy signing secret' })).toBeVisible();
		answer(Response.json({ key: KEY }));

		await expect.element(page.getByRole('button', { name: 'Signing secret copied' })).toBeVisible();
		expect(written).toEqual([KEY]);
		await expect.element(page.getByLabelText('Signing secret, hidden')).toBeVisible();
		await expect.element(page.getByText(KEY)).not.toBeInTheDocument();

		await page.getByRole('button', { name: 'Reveal' }).click();
		await expect.element(page.getByText(KEY)).toBeVisible();
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('does not claim a copy when the secret could not be loaded', async () => {
		stubSecret(() => new Response(null, { status: 502 }));
		const { written } = stubClipboard();
		await render(SigningSecret, { id: 'ep_1' });

		await page.getByRole('button', { name: 'Copy signing secret' }).click();
		await expect.element(page.getByText(/Could not load the signing secret/)).toBeVisible();
		await expect
			.element(page.getByRole('button', { name: 'Signing secret copied' }))
			.not.toBeInTheDocument();
		expect(written).toEqual([]);
	});
});
