<script lang="ts">
	import { page } from '$app/state';
	import { MICRO } from '$lib/components/ui/typography';
	import { avatarTone, fullName, initials } from '$lib/users/avatar';

	// The layout load already carries it, so this costs no request.
	const developer = $derived(page.data.developer);
	const name = $derived(developer ? fullName(developer) : '');
</script>

{#if developer}
	<div class="flex items-center gap-2.5 px-3 py-2">
		<span
			aria-hidden="true"
			class="grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-semibold
				{avatarTone(developer.id)}"
		>
			{initials(developer)}
		</span>

		<!-- Which account this is, on every screen: it was answerable nowhere
		     before, and "whose dashboard am I looking at" matters most for the
		     buttons right under it. -->
		<div class="min-w-0">
			<span class="sr-only">Signed in as</span>
			{#if name}
				<span class="block truncate text-sm font-medium text-foreground">{name}</span>
			{/if}
			<span class="block truncate {MICRO}" title={developer.email}>{developer.email}</span>
		</div>
	</div>
{/if}
