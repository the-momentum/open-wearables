import { createFileRoute, Link } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
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
import { Search, Eye, Trash2, Plus, Copy, Check } from 'lucide-react';
import { useUsers, useDeleteUser, useCreateUser } from '@/hooks/api/use-users';
import { TableSkeleton } from '@/components/common/table-skeleton';
import { ErrorState } from '@/components/common/error-state';
import { EmptyState } from '@/components/common/empty-state';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';

export const Route = createFileRoute('/_authenticated/users/')({
  component: UsersPage,
});

function UsersPage() {
  const [search, setSearch] = useState('');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { data: users, isLoading, error, refetch } = useUsers({ search });
  const deleteUser = useDeleteUser();
  const createUser = useCreateUser();

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    if (!search) return users;

    const searchLower = search.toLowerCase();
    return users.filter((user) => user.id.toLowerCase().includes(searchLower));
  }, [users, search]);

  const handleCopyId = async (id: string) => {
    await navigator.clipboard.writeText(id);
    setCopiedId(id);
    toast.success('User ID copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCreateUser = async () => {
    try {
      await createUser.mutateAsync({});
      setIsCreateDialogOpen(false);
    } catch {}
  };

  const handleDeleteUser = async () => {
    if (deleteUserId) {
      try {
        await deleteUser.mutateAsync(deleteUserId);
        setDeleteUserId(null);
      } catch {}
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
          <div className="relative mb-4">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by user ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
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
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(user.created_at), {
                          addSuffix: true,
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Link to={`/users/${user.id}`}>
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

      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New User</DialogTitle>
            <DialogDescription>
              A new user ID will be automatically generated. Use this ID to
              connect wearable devices and collect health data.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              After creating the user, you can:
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground mt-2 space-y-1">
              <li>Generate connection links for wearable devices</li>
              <li>View health data from connected devices</li>
              <li>Set up automations based on health metrics</li>
            </ul>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
            >
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
