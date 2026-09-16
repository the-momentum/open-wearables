<script lang="ts">
	import { version } from '$app/environment';
</script>

<!-- tabular-nums keeps the value from shifting between releases. -->
<div class="mt-2 flex items-center justify-between px-3 text-[0.6875rem]">
	<span class="text-muted-foreground/70">Version</span>
	<span class="font-mono font-medium text-foreground tabular-nums">{version}</span>
</div>
