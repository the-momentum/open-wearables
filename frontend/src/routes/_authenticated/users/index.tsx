import { createFileRoute, Link } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search, Eye, Trash2, Plus, Copy, Check } from 'lucide-react';
import { useUsers, useDeleteUser, useCreateUser } from '@/hooks/api/use-users';
import { TableSkeleton } from '@/components/common/table-skeleton';
import { ErrorState } from '@/components/common/error-state';
import { EmptyState } from '@/components/common/empty-state';
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
      const fullName = `${user.first_name || ''} ${user.last_name || ''}`.toLowerCase();

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
      <div className="flex-1 p-8">
        <div className="mb-4">
          <h2 className="text-3xl font-bold tracking-tight">Users</h2>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>All Users</CardTitle>
          </CardHeader>
          <CardContent>
            <TableSkeleton rows={5} columns={3} />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-8">
        <ErrorState
          title="Failed to load users"
          message="An error occurred while loading the users list. Please try again."
          onRetry={refetch}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Users</h2>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add User
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users</CardTitle>
          <CardDescription>
            Manage your platform users and their wearable connections
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={
                  searchField === 'all'
                    ? 'Search users...'
                    : `Search by ${searchField.replace('_', ' ')}...`
                }
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select
              value={searchField}
              onValueChange={(value) => setSearchField(value as SearchField)}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Search field" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All fields</SelectItem>
                <SelectItem value="id">User ID</SelectItem>
                <SelectItem value="client_user_id">Client User ID</SelectItem>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="name">Name</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {filteredUsers.length === 0 ? (
            <EmptyState
              title="No users found"
              message={
                search
                  ? 'No users match your search criteria.'
                  : 'No users have been created yet. Create your first user to start collecting health data.'
              }
              action={
                !search ? (
                  <Button onClick={() => setIsCreateDialogOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create First User
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User ID</TableHead>
                    <TableHead>Client User ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <code className="font-mono text-sm bg-muted px-2 py-1 rounded">
                            {truncateId(user.id)}
                          </code>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={() => handleCopyId(user.id)}
                          >
                            {copiedId === user.id ? (
                              <Check className="h-3 w-3 text-green-500" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="font-mono text-sm bg-muted px-2 py-1 rounded">
                          {truncateId(user.client_user_id)}
                        </code>
                      </TableCell>
                      <TableCell>
                        {user.first_name || user.last_name ? (
                          <span>
                            {[user.first_name, user.last_name]
                              .filter(Boolean)
                              .join(' ')}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {user.email ? (
                          <span className="text-sm">{user.email}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(user.created_at), {
                          addSuffix: true,
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Link
                            to="/users/$userId"
                            params={{ userId: user.id }}
                          >
                            <Button variant="ghost" size="icon">
                              <Eye className="h-4 w-4" />
                            </Button>
                          </Link>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteUserId(user.id)}
                            disabled={deleteUser.isPending}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isCreateDialogOpen} onOpenChange={handleCloseCreateDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Create New User</DialogTitle>
            <DialogDescription>
              Create a new user to connect wearable devices and collect health
              data. A unique system ID will be auto-generated.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="client_user_id">
                Client User ID <span className="text-destructive">*</span>
              </Label>
              <Input
                id="client_user_id"
                placeholder="e.g., user_12345 or external system ID"
                value={formData.client_user_id}
                onChange={(e) =>
                  setFormData({ ...formData, client_user_id: e.target.value })
                }
                maxLength={255}
              />
              {formErrors.client_user_id && (
                <p className="text-sm text-destructive">
                  {formErrors.client_user_id}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Your unique identifier for this user (max 255 characters)
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="first_name">First Name</Label>
                <Input
                  id="first_name"
                  placeholder="John"
                  value={formData.first_name || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, first_name: e.target.value })
                  }
                  maxLength={100}
                />
                {formErrors.first_name && (
                  <p className="text-sm text-destructive">
                    {formErrors.first_name}
                  </p>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="last_name">Last Name</Label>
                <Input
                  id="last_name"
                  placeholder="Doe"
                  value={formData.last_name || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, last_name: e.target.value })
                  }
                  maxLength={100}
                />
                {formErrors.last_name && (
                  <p className="text-sm text-destructive">
                    {formErrors.last_name}
                  </p>
                )}
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="john.doe@example.com"
                value={formData.email || ''}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
              {formErrors.email && (
                <p className="text-sm text-destructive">{formErrors.email}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseCreateDialog}>
              Cancel
            </Button>
            <Button onClick={handleCreateUser} disabled={createUser.isPending}>
              {createUser.isPending ? 'Creating...' : 'Create User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteUserId !== null}
        onOpenChange={(open) => !open && setDeleteUserId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete User?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently delete the
              user and all associated data including:
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>All wearable device connections</li>
              <li>All health data (heart rate, sleep, activity)</li>
              <li>All automation triggers for this user</li>
            </ul>
            {deleteUserId && (
              <div className="mt-4 p-3 bg-muted rounded-md">
                <p className="text-sm text-muted-foreground">User ID:</p>
                <code className="font-mono text-sm">{deleteUserId}</code>
              </div>
            )}
          </div>
          <DialogFooter>
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
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
