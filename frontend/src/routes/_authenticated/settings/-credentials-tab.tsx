import { useState } from 'react';
import {
  Plus,
  Eye,
  EyeOff,
  Copy,
  Trash2,
  Key,
  Globe,
  Pencil,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  useUpdateApiKey,
} from '@/hooks/api/use-credentials';
import type { ApiKey } from '@/lib/api/types';
import { copyToClipboard } from '@/lib/utils/clipboard';
import { API_CONFIG } from '@/lib/api/config';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export function CredentialsTab() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [keyName, setKeyName] = useState('');
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [renameKeyName, setRenameKeyName] = useState('');

  const { data: apiKeys, isLoading, error, refetch } = useApiKeys();
  const createMutation = useCreateApiKey();
  const deleteMutation = useDeleteApiKey();
  const updateMutation = useUpdateApiKey();

  const handleCreate = async () => {
    if (!keyName.trim()) {
      toast.error('Please enter a key name');
      return;
    }

    const newKey = await createMutation.mutateAsync({ name: keyName });
    setIsCreateDialogOpen(false);
    setKeyName('');

    setVisibleKeys((prev) => new Set(prev).add(newKey.id));
  };

  const handleDelete = async (id: string) => {
    if (
      confirm(
        'Are you sure you want to delete this API key? This action cannot be undone.'
      )
    ) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const openRenameDialog = (key: ApiKey) => {
    setEditingKey(key);
    setRenameKeyName(key.name);
  };

  const handleRenameSubmit = async () => {
    if (!editingKey) return;
    if (!renameKeyName.trim()) {
      toast.error('Please enter a key name');
      return;
    }

    await updateMutation.mutateAsync({
      id: editingKey.id,
      data: { name: renameKeyName.trim() },
    });
    setEditingKey(null);
    setRenameKeyName('');
  };

  const toggleKeyVisibility = (id: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const maskKey = (key: string) => {
    if (key.length < 10) return '****';
    return key.substring(0, 10) + '****' + key.substring(key.length - 4);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-zinc-800 rounded-md w-full" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-zinc-800/50 rounded-md" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-zinc-400 mb-4">Failed to load API keys</p>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-medium text-white">API Credentials</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Manage your API keys and widget embed codes
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="h-4 w-4" />
          Create API Key
        </Button>
      </div>

      {/* API Base URL */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Globe className="h-4 w-4 text-zinc-500" />
            <div>
              <p className="text-xs text-zinc-500">API Base URL</p>
              <code className="font-mono text-sm text-zinc-300">
                {API_CONFIG.baseUrl}
              </code>
            </div>
          </div>
          <Button
            variant="ghost-faded"
            size="icon-sm"
            aria-label="Copy API URL"
            onClick={() =>
              copyToClipboard(API_CONFIG.baseUrl, 'API URL copied')
            }
          >
            <Copy className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* API Keys Table */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h3 className="text-sm font-medium text-white">API Keys</h3>
          <p className="text-xs text-zinc-500 mt-1">
            Use these keys to authenticate API requests and embed widgets
          </p>
        </div>

        {apiKeys && apiKeys.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Key
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {apiKeys.map((key) => (
                  <tr
                    key={key.id}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-medium text-zinc-300">
                      {key.name}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <code className="font-mono text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded">
                          {visibleKeys.has(key.id) ? key.id : maskKey(key.id)}
                        </code>
                        <Button
                          variant="ghost-faded"
                          size="icon-sm"
                          onClick={() => toggleKeyVisibility(key.id)}
                        >
                          {visibleKeys.has(key.id) ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost-faded"
                          size="icon-sm"
                          onClick={() => copyToClipboard(key.id)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-zinc-500">
                      {formatDate(key.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          aria-label="Rename API key"
                          onClick={() => openRenameDialog(key)}
                        >
                          <Pencil className="h-4 w-4" aria-hidden />
                        </Button>
                        <Button
                          variant="destructive-outline"
                          size="icon"
                          onClick={() => handleDelete(key.id)}
                          disabled={deleteMutation.isPending}
                          aria-label="Delete API key"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center">
            <Key className="h-12 w-12 text-zinc-700 mx-auto mb-4" />
            <p className="text-zinc-400 mb-2">No API keys yet</p>
            <p className="text-sm text-zinc-500 mb-4">
              Create your first key to get started
            </p>
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(true)}
            >
              <Plus className="h-4 w-4" />
              Create API Key
            </Button>
          </div>
        )}
      </div>

      {/* Rename API key */}
      <Dialog
        open={editingKey !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditingKey(null);
            setRenameKeyName('');
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Rename API Key</DialogTitle>
            <DialogDescription>
              Update the display name for this API key
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="rename_key_name" className="text-zinc-300">
              Key Name
            </Label>
            <Input
              id="rename_key_name"
              type="text"
              placeholder="e.g., Production API Key"
              value={renameKeyName}
              onChange={(e) => setRenameKeyName(e.target.value)}
              className="bg-zinc-800 border-zinc-700"
            />
            <p className="text-[10px] text-zinc-600">
              A descriptive name to identify this key
            </p>
          </div>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setEditingKey(null);
                setRenameKeyName('');
              }}
              disabled={updateMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRenameSubmit}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create New API Key</DialogTitle>
            <DialogDescription>
              Generate a new API key for your application
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="key_name" className="text-zinc-300">
              Key Name
            </Label>
            <Input
              id="key_name"
              type="text"
              placeholder="e.g., Production API Key"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              className="bg-zinc-800 border-zinc-700"
            />
            <p className="text-[10px] text-zinc-600">
              A descriptive name to identify this key
            </p>
          </div>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateDialogOpen(false);
                setKeyName('');
              }}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Key'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
