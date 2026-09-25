<script lang="ts">
	import { goto } from '$app/navigation';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import { PAGE_SIZES, isPageSize, type PageSize } from '$lib/lists/pagination';

	let { size, hrefFor }: { size: number; hrefFor: (size: PageSize) => string } = $props();

	const options = PAGE_SIZES.map((value) => ({ value, label: String(value) }));
</script>

<!-- A size change has to reach the server: the page it lands on depends on it. -->
<FilterSelect
	label="Per page"
	value={size}
	{options}
	onselect={(next) => {
		const parsed = Number(next);
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
		if (isPageSize(parsed)) goto(hrefFor(parsed));
	}}
/>
