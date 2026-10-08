import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ProviderMark from './ProviderMark.svelte';

describe('ProviderMark', () => {
	it('draws Open Wearables by its logo, and a provider by its initials', async () => {
		const own = render(ProviderMark, { provider: 'internal', label: 'OW' });
		expect(own.container.querySelector('svg')).not.toBeNull();
		expect(own.container.textContent?.trim()).toBe('');

		const oura = render(ProviderMark, { provider: 'oura', label: 'Oura' });
		expect(oura.container.querySelector('svg')).toBeNull();
		expect(oura.container.textContent?.trim()).toBe('OU');
	});
});
