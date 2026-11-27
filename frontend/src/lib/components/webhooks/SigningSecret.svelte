<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import Button from '$lib/components/ui/Button.svelte';
	import { INLINE_LINK, MICRO, MONO } from '$lib/components/ui/typography';
	import { createCopier } from '$lib/utils/clipboard.svelte';
	import { fetchSigningSecret, MASKED_SECRET } from '$lib/webhooks/secret';

	let { id }: { id: string } = $props();

	const VERIFY_DOCS =
		'https://openwearables.io/docs/api-reference/guides/webhooks#signature-verification';

	const copier = createCopier();

	// Asked for once, on the first reveal or copy, and shared by both after that.
	let pending: Promise<string> | null = null;
	let key = $state<string | null>(null);
	let shown = $state(false);
	let loading = $state(false);
	let failed = $state(false);

	function load(): Promise<string> {
		if (!pending) {
			loading = true;
			failed = false;
			pending = fetchSigningSecret(id)
				.then((value) => (key = value))
				.catch((error) => {
					// A failed request is not cached: the next click tries again.
					pending = null;
					failed = true;
					throw error;
				})
				.finally(() => (loading = false));
		}
		return pending;
	}

	async function toggle() {
		if (shown) {
			shown = false;
			return;
		}
		try {
			await load();
			shown = true;
		} catch {
			// `failed` already says so beside the field.
		}
	}

	function copy() {
		// Already here: a plain write. Not yet: the pending text goes into the
		// clipboard item, since Safari drops the click's permission across an await.
		if (key) copier.copy(key);
		else copier.copyPending(load());
	}
</script>

<div class="flex flex-col gap-1.5">
	<span class={MICRO}>Signing secret</span>

	<div class="flex flex-wrap items-center gap-2">
		<code
			class="min-w-0 flex-1 truncate rounded-lg border border-border bg-surface-muted px-2.5 py-[9px]
				{MONO} {shown ? 'select-all' : 'text-muted-foreground select-none'}"
			aria-label={shown ? 'Signing secret' : 'Signing secret, hidden'}
		>
			{shown && key ? key : MASKED_SECRET}
		</code>

		<div class="flex shrink-0 items-center gap-1.5">
			<Button
				variant="outline"
				size="sm"
				onclick={toggle}
				disabled={loading}
				aria-pressed={shown}
				class="text-muted-foreground hover:text-foreground"
			>
				{#if shown}
					<EyeOff size={13} aria-hidden="true" />
					Hide
				{:else}
					<Eye size={13} aria-hidden="true" />
					{loading ? 'Loading…' : 'Reveal'}
				{/if}
			</Button>

			<Button
				variant="outline"
				size="sm"
				onclick={copy}
				aria-label={copier.copied ? 'Signing secret copied' : 'Copy signing secret'}
				class="text-muted-foreground hover:text-foreground"
			>
				{#if copier.copied}
					<Check size={13} aria-hidden="true" class="text-success" />
					Copied
				{:else}
					<Copy size={13} aria-hidden="true" />
					Copy
				{/if}
			</Button>
		</div>
	</div>

	{#if failed}
		<span class="{MICRO} text-danger">Could not load the signing secret. Try again.</span>
	{:else}
		<span class={MICRO}>
			Use it to check the <code class="font-mono">svix-signature</code> header, so you only act on
			deliveries that came from Open Wearables.
			<a href={VERIFY_DOCS} target="_blank" rel="noreferrer" class={INLINE_LINK}>How to verify</a>
		</span>
	{/if}
</div>
