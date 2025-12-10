import { createFileRoute } from '@tanstack/react-router';
import { useState, useCallback } from 'react';
import { Plus, Users as UsersIcon } from 'lucide-react';
import { useUsers, useDeleteUser, useCreateUser } from '@/hooks/api/use-users';
import type { UserCreate, UserQueryParams } from '@/lib/api/types';
import { UsersTable } from '@/components/users/users-table';
import { Button } from '@/components/ui/button';

const initialFormState: UserCreate = {
  external_user_id: '',
  first_name: '',
  last_name: '',
  email: '',
};

const DEFAULT_PAGE_SIZE = 9;

export const Route = createFileRoute('/_authenticated/users/')({
  component: UsersPage,
});

function UsersPage() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [formData, setFormData] = useState<UserCreate>(initialFormState);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [queryParams, setQueryParams] = useState<UserQueryParams>({
    page: 1,
    limit: DEFAULT_PAGE_SIZE,
    sort_by: 'created_at',
    sort_order: 'desc',
  });

  const { data, isLoading, isFetching, error, refetch } = useUsers(queryParams);
  const deleteUser = useDeleteUser();
  const createUser = useCreateUser();

  const handleQueryChange = useCallback((params: UserQueryParams) => {
    setQueryParams(params);
  }, []);

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (formData.external_user_id && formData.external_user_id.length > 255) {
      errors.external_user_id =
        'External User ID must be 255 characters or less';
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
      external_user_id: formData.external_user_id?.trim() || null,
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
          <Button onClick={() => refetch()}>Retry</Button>
        </div>
      </div>
    );
  }

  const users = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageCount = data?.pages ?? 0;

  return (
    <div className="p-8">
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

      {total > 0 || queryParams.search ? (
        <UsersTable
          data={users}
          total={total}
          page={queryParams.page ?? 1}
          pageSize={queryParams.limit ?? DEFAULT_PAGE_SIZE}
          pageCount={pageCount}
          isLoading={isFetching}
          onDelete={setDeleteUserId}
          isDeleting={deleteUser.isPending}
          onQueryChange={handleQueryChange}
        />
      ) : (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
          <UsersIcon className="h-12 w-12 text-zinc-700 mx-auto mb-4" />
          <p className="text-zinc-400 mb-2">No users found</p>
          <Button
            variant="outline"
            onClick={() => setIsCreateDialogOpen(true)}
            className="mt-4"
          >
            <Plus className="h-4 w-4" />
            Create First User
          </Button>
        </div>
      )}

      {isCreateDialogOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-zinc-800">
              <h2 className="text-lg font-medium text-white">
                Create New User
              </h2>
              <p className="text-sm text-zinc-500 mt-1">
                Create a new user to connect wearable devices and collect health
                data.
              </p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  External User ID
                </label>
                <input
                  type="text"
                  placeholder="e.g., user_12345 or external system ID"
                  value={formData.external_user_id || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      external_user_id: e.target.value,
                    })
                  }
                  maxLength={255}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                />
                {formErrors.external_user_id && (
                  <p className="text-xs text-red-500">
                    {formErrors.external_user_id}
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
                <label className="text-xs font-medium text-zinc-300">
                  Email
                </label>
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
              <Button variant="outline" onClick={handleCloseCreateDialog}>
                Cancel
              </Button>
              <Button
                onClick={handleCreateUser}
                disabled={createUser.isPending}
              >
                {createUser.isPending ? 'Creating...' : 'Create User'}
              </Button>
            </div>
          </div>
        </div>
      )}

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
              <Button variant="outline" onClick={() => setDeleteUserId(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteUser}
                disabled={deleteUser.isPending}
              >
                {deleteUser.isPending ? 'Deleting...' : 'Delete User'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
