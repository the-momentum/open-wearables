<script lang="ts">
	import { page } from '$app/state';
	import { MICRO } from '$lib/components/ui/typography';
	import AccountAvatar from './AccountAvatar.svelte';

	// The layout load already carries it, so this costs no request.
	const developer = $derived(page.data.developer);
</script>

{#if developer}
	<div class="flex items-center gap-2.5 px-3 py-2">
		<AccountAvatar {developer} />

		<!-- Which account this is, on every screen, by the one field every account carries. -->
		<p class="min-w-0 truncate {MICRO}" title={developer.email}>
			<span class="sr-only">Signed in as</span>
			{developer.email}
		</p>
	</div>
{/if}
