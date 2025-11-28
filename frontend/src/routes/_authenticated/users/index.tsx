import { createFileRoute, Link } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import {
  Search,
  Eye,
  Trash2,
  Plus,
  Copy,
  Check,
  ChevronDown,
  Users as UsersIcon,
} from 'lucide-react';
import { useUsers, useDeleteUser, useCreateUser } from '@/hooks/api/use-users';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import type { UserCreate } from '@/lib/api/types';

type SearchField = 'all' | 'id' | 'email' | 'name' | 'client_user_id';

const initialFormState: UserCreate = {
  client_user_id: '',
  first_name: '',
  last_name: '',
  email: '',
};

export const Route = createFileRoute('/_authenticated/users/')({
  component: UsersPage,
});

function UsersPage() {
  const [search, setSearch] = useState('');
  const [searchField, setSearchField] = useState<SearchField>('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [formData, setFormData] = useState<UserCreate>(initialFormState);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const { data: users, isLoading, error, refetch } = useUsers({ search });
  const deleteUser = useDeleteUser();
  const createUser = useCreateUser();

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    if (!search) return users;

    const searchLower = search.toLowerCase();
    return users.filter((user) => {
      const fullName =
        `${user.first_name || ''} ${user.last_name || ''}`.toLowerCase();

      switch (searchField) {
        case 'id':
          return user.id.toLowerCase().includes(searchLower);
        case 'email':
          return user.email?.toLowerCase().includes(searchLower);
        case 'name':
          return fullName.includes(searchLower);
        case 'client_user_id':
          return user.client_user_id.toLowerCase().includes(searchLower);
        case 'all':
        default:
          return (
            user.id.toLowerCase().includes(searchLower) ||
            user.email?.toLowerCase().includes(searchLower) ||
            fullName.includes(searchLower) ||
            user.client_user_id.toLowerCase().includes(searchLower)
          );
      }
    });
  }, [users, search, searchField]);

  const handleCopyId = async (id: string) => {
    await navigator.clipboard.writeText(id);
    setCopiedId(id);
    toast.success('User ID copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.client_user_id.trim()) {
      errors.client_user_id = 'Client User ID is required';
    } else if (formData.client_user_id.length > 255) {
      errors.client_user_id = 'Client User ID must be 255 characters or less';
    }

    if (formData.first_name && formData.first_name.length > 100) {
      errors.first_name = 'First name must be 100 characters or less';
    }

    if (formData.last_name && formData.last_name.length > 100) {
      errors.last_name = 'Last name must be 100 characters or less';
    }

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'Please enter a valid email address';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleCreateUser = () => {
    if (!validateForm()) return;

    const payload: UserCreate = {
      client_user_id: formData.client_user_id.trim(),
      first_name: formData.first_name?.trim() || null,
      last_name: formData.last_name?.trim() || null,
      email: formData.email?.trim() || null,
    };

    createUser.mutate(payload, {
      onSuccess: () => {
        setIsCreateDialogOpen(false);
        setFormData(initialFormState);
        setFormErrors({});
      },
    });
  };

  const handleCloseCreateDialog = () => {
    setIsCreateDialogOpen(false);
    setFormData(initialFormState);
    setFormErrors({});
  };

  const handleDeleteUser = () => {
    if (deleteUserId) {
      deleteUser.mutate(deleteUserId, {
        onSuccess: () => {
          setDeleteUserId(null);
        },
      });
    }
  };

  const truncateId = (id: string) => {
    if (id.length <= 12) return id;
    return `${id.slice(0, 8)}...${id.slice(-4)}`;
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-medium text-white">Users</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Manage your platform users
          </p>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-10 bg-zinc-800 rounded-md w-full" />
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 bg-zinc-800/50 rounded-md" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
          <p className="text-zinc-400 mb-4">
            Failed to load users. Please try again.
          </p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-medium text-white">Users</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Manage your platform users and their wearable connections
          </p>
        </div>
        <button
          onClick={() => setIsCreateDialogOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add User
        </button>
      </div>

      {/* Main Card */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        {/* Search Bar */}
        <div className="p-4 border-b border-zinc-800">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
              <input
                type="text"
                placeholder={
                  searchField === 'all'
                    ? 'Search users...'
                    : `Search by ${searchField.replace('_', ' ')}...`
                }
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-md pl-9 pr-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all"
              />
            </div>
            <div className="relative">
              <select
                value={searchField}
                onChange={(e) => setSearchField(e.target.value as SearchField)}
                className="appearance-none bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 pr-8 text-sm text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all cursor-pointer"
              >
                <option value="all">All fields</option>
                <option value="id">User ID</option>
                <option value="client_user_id">Client User ID</option>
                <option value="email">Email</option>
                <option value="name">Name</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Table */}
        {filteredUsers.length === 0 ? (
          <div className="p-12 text-center">
            <UsersIcon className="h-12 w-12 text-zinc-700 mx-auto mb-4" />
            <p className="text-zinc-400 mb-2">
              {search ? 'No users match your search criteria.' : 'No users found'}
            </p>
            {!search && (
              <button
                onClick={() => setIsCreateDialogOpen(true)}
                className="mt-4 flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors mx-auto"
              >
                <Plus className="h-4 w-4" />
                Create First User
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800 text-left">
                  <th className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    User ID
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Client User ID
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {filteredUsers.map((user) => (
                  <tr
                    key={user.id}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <code className="font-mono text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded">
                          {truncateId(user.id)}
                        </code>
                        <button
                          onClick={() => handleCopyId(user.id)}
                          className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          {copiedId === user.id ? (
                            <Check className="h-3 w-3 text-emerald-500" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <code className="font-mono text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded">
                        {truncateId(user.client_user_id)}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-300">
                      {user.first_name || user.last_name ? (
                        <span>
                          {[user.first_name, user.last_name]
                            .filter(Boolean)
                            .join(' ')}
                        </span>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-400">
                      {user.email || <span className="text-zinc-600">—</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">
                      {formatDistanceToNow(new Date(user.created_at), {
                        addSuffix: true,
                      })}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Link
                          to="/users/$userId"
                          params={{ userId: user.id }}
                          className="p-2 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
                        >
                          <Eye className="h-4 w-4" />
                        </Link>
                        <button
                          onClick={() => setDeleteUserId(user.id)}
                          disabled={deleteUser.isPending}
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
        )}
      </div>

      {/* Create User Dialog */}
      {isCreateDialogOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-zinc-800">
              <h2 className="text-lg font-medium text-white">Create New User</h2>
              <p className="text-sm text-zinc-500 mt-1">
                Create a new user to connect wearable devices and collect health
                data.
              </p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Client User ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g., user_12345 or external system ID"
                  value={formData.client_user_id}
                  onChange={(e) =>
                    setFormData({ ...formData, client_user_id: e.target.value })
                  }
                  maxLength={255}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                />
                {formErrors.client_user_id && (
                  <p className="text-xs text-red-500">
                    {formErrors.client_user_id}
                  </p>
                )}
                <p className="text-[10px] text-zinc-600">
                  Your unique identifier for this user (max 255 characters)
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">
                    First Name
                  </label>
                  <input
                    type="text"
                    placeholder="John"
                    value={formData.first_name || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, first_name: e.target.value })
                    }
                    maxLength={100}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                  />
                  {formErrors.first_name && (
                    <p className="text-xs text-red-500">
                      {formErrors.first_name}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">
                    Last Name
                  </label>
                  <input
                    type="text"
                    placeholder="Doe"
                    value={formData.last_name || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, last_name: e.target.value })
                    }
                    maxLength={100}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                  />
                  {formErrors.last_name && (
                    <p className="text-xs text-red-500">
                      {formErrors.last_name}
                    </p>
                  )}
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">Email</label>
                <input
                  type="email"
                  placeholder="john.doe@example.com"
                  value={formData.email || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                />
                {formErrors.email && (
                  <p className="text-xs text-red-500">{formErrors.email}</p>
                )}
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3">
              <button
                onClick={handleCloseCreateDialog}
                className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateUser}
                disabled={createUser.isPending}
                className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-50"
              >
                {createUser.isPending ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteUserId && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-zinc-800">
              <h2 className="text-lg font-medium text-white">Delete User?</h2>
              <p className="text-sm text-zinc-500 mt-1">
                This action cannot be undone. This will permanently delete the
                user and all associated data including:
              </p>
            </div>
            <div className="p-6">
              <ul className="list-disc list-inside text-sm text-zinc-500 space-y-1">
                <li>All wearable device connections</li>
                <li>All health data (heart rate, sleep, activity)</li>
                <li>All automation triggers for this user</li>
              </ul>
              <div className="mt-4 p-3 bg-zinc-800 rounded-md">
                <p className="text-xs text-zinc-500">User ID:</p>
                <code className="font-mono text-sm text-zinc-300">
                  {deleteUserId}
                </code>
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3">
              <button
                onClick={() => setDeleteUserId(null)}
                className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteUser}
                disabled={deleteUser.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleteUser.isPending ? 'Deleting...' : 'Delete User'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
