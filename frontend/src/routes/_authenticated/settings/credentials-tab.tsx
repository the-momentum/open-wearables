import { useState } from 'react';
import { Plus, Eye, EyeOff, Copy, Trash2, Key } from 'lucide-react';
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
} from '@/hooks/api/use-credentials';
import { toast } from 'sonner';

export function CredentialsTab() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [keyName, setKeyName] = useState('');

  const { data: apiKeys, isLoading, error, refetch } = useApiKeys();
  const createMutation = useCreateApiKey();
  const deleteMutation = useDeleteApiKey();

  const handleCreate = async () => {
    if (!keyName.trim()) {
      toast.error('Please enter a key name');
      return;
    }

    const newKey = await createMutation.mutateAsync({ name: keyName });
    setIsCreateDialogOpen(false);
    setKeyName('');

    toast.success('API key created successfully');
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

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
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
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          Retry
        </button>
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
        <button
          onClick={() => setIsCreateDialogOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Create API Key
        </button>
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
                        <button
                          onClick={() => toggleKeyVisibility(key.id)}
                          className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          {visibleKeys.has(key.id) ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                        <button
                          onClick={() => copyToClipboard(key.id)}
                          className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-zinc-500">
                      {formatDate(key.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end">
                        <button
                          onClick={() => handleDelete(key.id)}
                          disabled={deleteMutation.isPending}
                          className="p-2 text-zinc-500 hover:text-red-400 hover:bg-zinc-800 rounded-md transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
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
            <button
              onClick={() => setIsCreateDialogOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Create API Key
            </button>
          </div>
        )}
      </div>

      {/* Create Dialog */}
      {isCreateDialogOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-zinc-800">
              <h2 className="text-lg font-medium text-white">
                Create New API Key
              </h2>
              <p className="text-sm text-zinc-500 mt-1">
                Generate a new API key for your application
              </p>
            </div>
            <div className="p-6">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Key Name
                </label>
                <input
                  type="text"
                  placeholder="e.g., Production API Key"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                />
                <p className="text-[10px] text-zinc-600">
                  A descriptive name to identify this key
                </p>
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3">
              <button
                onClick={() => {
                  setIsCreateDialogOpen(false);
                  setKeyName('');
                }}
                disabled={createMutation.isPending}
                className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={createMutation.isPending}
                className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating...' : 'Create Key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

