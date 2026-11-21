<script lang="ts">
	import { page } from '$app/state';
	import { MICRO } from '$lib/components/ui/typography';
	import { fullName } from '$lib/users/avatar';
	import AccountAvatar from './AccountAvatar.svelte';

	// The layout load already carries it, so this costs no request.
	const developer = $derived(page.data.developer);
	const name = $derived(developer ? fullName(developer) : '');
</script>

{#if developer}
	<div class="flex items-center gap-2.5 px-3 py-2">
		<AccountAvatar {developer} />

		<!-- Which account this is, on every screen: "whose dashboard am I looking
		     at" matters most for the buttons right under it. -->
		<div class="min-w-0">
			<span class="sr-only">Signed in as</span>
			{#if name}
				<span class="block truncate text-sm font-medium text-foreground">{name}</span>
			{/if}
			<span class="block truncate {MICRO}" title={developer.email}>{developer.email}</span>
		</div>
	</div>
{/if}
