<script lang="ts">
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
</script>

<!-- Filters, then content: the rough shape of any tab. -->
<div class="flex flex-col gap-4" aria-busy="true">
	<Skeleton class="h-10 w-full max-w-md" />
	<Skeleton class="h-40" />
	<Skeleton class="h-24" />
	<Skeleton class="h-24" />
</div>
