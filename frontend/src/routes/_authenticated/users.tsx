import { createFileRoute } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Search, Eye, Trash2 } from 'lucide-react';
import { useUsers, useDeleteUser } from '@/hooks/api/use-users';
import { TableSkeleton } from '@/components/common/table-skeleton';
import { ErrorState } from '@/components/common/error-state';
import { EmptyState } from '@/components/common/empty-state';
import { formatDistanceToNow } from 'date-fns';

export const Route = createFileRoute('/_authenticated/users')({
  component: UsersPage,
});

function UsersPage() {
  const [search, setSearch] = useState('');
  const { data: users, isLoading, error, refetch } = useUsers({ search });
  const deleteUser = useDeleteUser();

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    if (!search) return users;

    const searchLower = search.toLowerCase();
    return users.filter(
      (user) =>
        user.name?.toLowerCase().includes(searchLower) ||
        user.email?.toLowerCase().includes(searchLower)
    );
  }, [users, search]);

  const getStatusColor = (
    status: string
  ): 'default' | 'destructive' | 'secondary' | 'outline' => {
    switch (status) {
      case 'active':
        return 'default';
      case 'error':
        return 'destructive';
      case 'pending':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (confirm('Are you sure you want to delete this user?')) {
      deleteUser.mutate(userId);
    }
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
            <TableSkeleton rows={5} columns={5} />
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
        <Button>Add User</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users</CardTitle>
          <CardDescription>
            Manage your platform users and their connections
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>

          {/* Empty State */}
          {filteredUsers.length === 0 ? (
            <EmptyState
              title="No users found"
              message={
                search
                  ? 'No users match your search criteria.'
                  : 'No users have been added yet.'
              }
            />
          ) : (
            /* Table */
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Connections</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Sync</TableHead>
                    <TableHead>Data Points</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user) => {
                    const connections =
                      (user.metadata?.connections as string[]) || [];
                    const status =
                      (user.metadata?.status as string) || 'pending';
                    const lastSync = user.metadata?.lastSync as string | null;
                    const dataPoints =
                      (user.metadata?.dataPoints as number) || 0;

                    return (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">
                          {user.name || 'Unnamed User'}
                        </TableCell>
                        <TableCell>{user.email || 'No email'}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {connections.length > 0 ? (
                              connections.map((conn) => (
                                <Badge key={conn} variant="outline">
                                  {conn}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-sm text-muted-foreground">
                                None
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getStatusColor(status)}>
                            {status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {lastSync
                            ? formatDistanceToNow(new Date(lastSync), {
                                addSuffix: true,
                              })
                            : 'Never'}
                        </TableCell>
                        <TableCell>
                          {dataPoints > 0
                            ? dataPoints >= 1000
                              ? `${(dataPoints / 1000).toFixed(1)}K`
                              : dataPoints
                            : '0'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => {
                                /* TODO: Navigate to user detail */
                              }}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteUser(user.id)}
                              disabled={deleteUser.isPending}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
