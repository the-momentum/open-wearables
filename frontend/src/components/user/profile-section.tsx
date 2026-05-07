import { useState, useEffect } from 'react';
import { Link as LinkIcon, Check, Copy, Pencil } from 'lucide-react';
import { useUserConnections } from '@/hooks/api/use-health';
import { useUser, useUpdateUser } from '@/hooks/api/use-users';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { formatDate, truncateId } from '@/lib/utils/format';
import { copyToClipboard } from '@/lib/utils/clipboard';
import { ConnectionCard } from '@/components/user/connection-card';
import { DataSummarySection } from '@/components/user/data-summary-section';
import { useSyncStatusStream, useSyncRuns } from '@/hooks/api/use-sync-status';

interface ProfileSectionProps {
  userId: string;
}

export function ProfileSection({ userId }: ProfileSectionProps) {
  const { data: user, isLoading: userLoading } = useUser(userId);
  const { data: connections, isLoading: connectionsLoading } =
    useUserConnections(userId);
  const { mutate: updateUser, isPending: isUpdating } = useUpdateUser();

  // Live sync stream – one SSE connection shared across all provider cards
  const { activeRuns } = useSyncStatusStream(userId);
  const { data: syncRuns } = useSyncRuns(userId, 30);

  const [copied, setCopied] = useState(false);
  const [copiedUserId, setCopiedUserId] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    external_user_id: '',
  });

  useEffect(() => {
    if (user) {
      setEditForm({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || '',
        external_user_id: user.external_user_id || '',
      });
    }
  }, [user]);

  const handleCopyUserId = async () => {
    const success = await copyToClipboard(
      userId,
      'User ID copied to clipboard'
    );
    if (success) {
      setCopiedUserId(true);
      setTimeout(() => setCopiedUserId(false), 2000);
    }
  };

  const handleCopyPairLink = async () => {
    const pairLink = `${window.location.origin}/users/${userId}/pair`;
    const success = await copyToClipboard(
      pairLink,
      'Pairing link copied to clipboard'
    );
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleEditSubmit = () => {
    updateUser(
      {
        id: userId,
        data: {
          first_name: editForm.first_name || null,
          last_name: editForm.last_name || null,
          email: editForm.email || null,
          external_user_id: editForm.external_user_id || null,
        },
      },
      {
        onSuccess: () => {
          setIsEditDialogOpen(false);
        },
      }
    );
  };

  return (
    <>
      <div className="space-y-6">
        {/* User Information */}
        <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-border/60 flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">
              User Information
            </h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditDialogOpen(true)}
              className="text-muted-foreground hover:text-foreground"
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </Button>
          </div>
          <div className="p-6">
            {userLoading ? (
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <div className="h-4 w-16 bg-muted/50 rounded animate-pulse" />
                  <div className="h-5 w-48 bg-muted rounded animate-pulse" />
                </div>
                <div className="space-y-2">
                  <div className="h-4 w-16 bg-muted/50 rounded animate-pulse" />
                  <div className="h-5 w-32 bg-muted rounded animate-pulse" />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">User ID</p>
                  <div className="flex items-center gap-1.5">
                    <code className="font-mono text-sm text-foreground/90 bg-muted px-2 py-1 rounded">
                      {truncateId(user?.id ?? '')}
                    </code>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={handleCopyUserId}
                    >
                      {copiedUserId ? (
                        <Check className="h-3 w-3 text-[hsl(var(--success-muted))]" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    External User ID
                  </p>
                  <code className="font-mono text-sm text-foreground/90 bg-muted px-2 py-1 rounded">
                    {user?.external_user_id || '—'}
                  </code>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Email</p>
                  <p className="text-sm text-foreground/90">
                    {user?.email || '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Created</p>
                  <p className="text-sm text-foreground/90">
                    {formatDate(user?.created_at)}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Connected Providers */}
        <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-border/60">
            <h2 className="text-sm font-medium text-foreground">
              Connected Providers
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Wearable devices and health platforms connected to this user
            </p>
          </div>
          <div className="p-6">
            {connectionsLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {[1, 2].map((i) => (
                  <div
                    key={i}
                    className="p-4 border border-border/60 rounded-lg space-y-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="h-6 w-24 bg-muted rounded animate-pulse" />
                      <div className="h-5 w-16 bg-muted/50 rounded animate-pulse" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-4 w-40 bg-muted/50 rounded animate-pulse" />
                      <div className="h-4 w-36 bg-muted/50 rounded animate-pulse" />
                    </div>
                  </div>
                ))}
              </div>
            ) : connections && connections.length > 0 ? (
              <div className="grid gap-6 grid-cols-[repeat(auto-fit,minmax(400px,1fr))]">
                {connections.map((connection) => {
                  const activeSync =
                    Array.from(activeRuns.values()).find(
                      (e) => e.provider === connection.provider
                    ) ?? null;
                  const recentRuns = (syncRuns ?? [])
                    .filter((r) => r.provider === connection.provider)
                    .slice(0, 10);
                  return (
                    <ConnectionCard
                      key={connection.id}
                      connection={connection}
                      activeSync={activeSync}
                      recentRuns={recentRuns}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">
                  No providers connected yet
                </p>
                <Button variant="outline" onClick={handleCopyPairLink}>
                  {copied ? (
                    <>
                      <Check className="h-4 w-4 text-[hsl(var(--success-muted))]" />
                      Link Copied!
                    </>
                  ) : (
                    <>
                      <LinkIcon className="h-4 w-4" />
                      Copy Pairing Link
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Data Summary */}
        <DataSummarySection userId={userId} />
      </div>

      {/* Edit User Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>Update user information</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name" className="text-foreground/90">
                  First Name
                </Label>
                <Input
                  id="first_name"
                  value={editForm.first_name}
                  onChange={(e) =>
                    setEditForm({ ...editForm, first_name: e.target.value })
                  }
                  placeholder="John"
                  className="bg-muted border-border"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name" className="text-foreground/90">
                  Last Name
                </Label>
                <Input
                  id="last_name"
                  value={editForm.last_name}
                  onChange={(e) =>
                    setEditForm({ ...editForm, last_name: e.target.value })
                  }
                  placeholder="Doe"
                  className="bg-muted border-border"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-foreground/90">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                value={editForm.email}
                onChange={(e) =>
                  setEditForm({ ...editForm, email: e.target.value })
                }
                placeholder="john@example.com"
                className="bg-muted border-border"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="external_user_id" className="text-foreground/90">
                External User ID
              </Label>
              <Input
                id="external_user_id"
                value={editForm.external_user_id}
                onChange={(e) =>
                  setEditForm({
                    ...editForm,
                    external_user_id: e.target.value,
                  })
                }
                placeholder="external-123"
                className="bg-muted border-border"
              />
              <p className="text-xs text-muted-foreground">
                Optional identifier from your system
              </p>
            </div>
          </div>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => setIsEditDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleEditSubmit} disabled={isUpdating}>
              {isUpdating ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
