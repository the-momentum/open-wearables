import { useState } from 'react';
import {
  Trash2,
  UserPlus,
  Users,
  Mail,
  RotateCw,
  Clock,
  Copy,
  Check,
} from 'lucide-react';
import { useDevelopers, useDeleteDeveloper } from '@/hooks/api/use-developers';
import {
  useInvitations,
  useCreateInvitation,
  useRevokeInvitation,
  useResendInvitation,
} from '@/hooks/api/use-invitations';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/use-auth';
import { isValidEmail } from '@/lib/utils';
import { copyToClipboard } from '@/lib/utils/clipboard';
import { truncateId } from '@/lib/utils/format';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

export function TeamTab() {
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    email: string;
  } | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<{
    id: string;
    email: string;
  } | null>(null);

  const { me } = useAuth();
  const {
    data: developers,
    isLoading: isLoadingDevelopers,
    error: developersError,
    refetch: refetchDevelopers,
  } = useDevelopers();
  const {
    data: invitations,
    isLoading: isLoadingInvitations,
    error: invitationsError,
    refetch: refetchInvitations,
  } = useInvitations();

  const deleteMutation = useDeleteDeveloper();
  const createInvitationMutation = useCreateInvitation();
  const revokeInvitationMutation = useRevokeInvitation();
  const resendInvitationMutation = useResendInvitation();

  const isLoading = isLoadingDevelopers || isLoadingInvitations;

  const handleCopyId = async (id: string) => {
    const success = await copyToClipboard(id, 'ID copied to clipboard');
    if (success) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const handleDelete = () => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id, {
        onSuccess: () => setDeleteTarget(null),
      });
    }
  };

  const handleInvite = () => {
    const email = inviteEmail.trim();
    if (!email || !isValidEmail(email)) {
      toast.error('Invalid email address');
      return;
    }

    createInvitationMutation.mutate(
      { email },
      {
        onSuccess: () => {
          setInviteEmail('');
          setIsInviteModalOpen(false);
        },
      }
    );
  };

  const handleRevokeInvitation = () => {
    if (revokeTarget) {
      revokeInvitationMutation.mutate(revokeTarget.id, {
        onSuccess: () => setRevokeTarget(null),
      });
    }
  };

  const handleResendInvitation = (id: string) => {
    resendInvitationMutation.mutate(id);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const isExpired = (expiresAt: string) => {
    return new Date(expiresAt) < new Date();
  };

  const activeInvitations = invitations?.filter((inv) => {
    if (inv.status === 'failed') return true;
    if (inv.status === 'pending' || inv.status === 'sent') {
      return !isExpired(inv.expires_at);
    }
    return false;
  });

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-muted rounded-md w-full" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-muted/50 rounded-md" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (developersError || invitationsError) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12 text-center">
        <p className="text-muted-foreground mb-4">Failed to load team data</p>
        <Button
          onClick={() => {
            refetchDevelopers();
            refetchInvitations();
          }}
        >
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-medium text-foreground">Team Members</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your team and their access
          </p>
        </div>
        <Button onClick={() => setIsInviteModalOpen(true)}>
          <UserPlus className="h-4 w-4" />
          Invite Member
        </Button>
      </div>

      {/* Pending Invitations */}
      {activeInvitations && activeInvitations.length > 0 && (
        <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-border/60">
            <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
              <Clock className="h-4 w-4 text-[hsl(var(--warning-muted))]" />
              Pending Invitations
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Invitations that are waiting to be accepted
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/60 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Sent
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Expires
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {activeInvitations.map((invitation) => (
                  <tr
                    key={invitation.id}
                    className="hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-medium text-foreground/90">
                      <div className="flex items-center gap-2">
                        <Mail className="h-4 w-4 text-muted-foreground" />
                        {invitation.email}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDate(invitation.created_at)}
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDate(invitation.expires_at)}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase ${
                          invitation.status === 'sent' ||
                          invitation.status === 'pending'
                            ? 'bg-[hsl(var(--success-muted)/0.15)] text-[hsl(var(--success-muted))]'
                            : invitation.status === 'failed'
                              ? 'bg-[hsl(var(--destructive-muted)/0.15)] text-[hsl(var(--destructive-muted))]'
                              : 'bg-[hsl(var(--warning-muted)/0.15)] text-[hsl(var(--warning-muted))]'
                        }`}
                      >
                        {invitation.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleResendInvitation(invitation.id)}
                          disabled={resendInvitationMutation.isPending}
                          title="Resend invitation"
                        >
                          <RotateCw className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive-outline"
                          size="icon"
                          onClick={() =>
                            setRevokeTarget({
                              id: invitation.id,
                              email: invitation.email,
                            })
                          }
                          disabled={revokeInvitationMutation.isPending}
                          title="Revoke invitation"
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
        </div>
      )}

      {/* Team Members Table */}
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border/60">
          <h3 className="text-sm font-medium text-foreground">Developers</h3>
          <p className="text-xs text-muted-foreground mt-1">
            All team members with access to this organization
          </p>
        </div>

        {developers && developers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/60 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    ID
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Created At
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {developers.map((developer) => (
                  <tr
                    key={developer.id}
                    className="hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm text-foreground/90">
                      {developer.first_name || developer.last_name ? (
                        <span>
                          {[developer.first_name, developer.last_name]
                            .filter(Boolean)
                            .join(' ')}
                        </span>
                      ) : (
                        <span className="text-muted-foreground/70">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-foreground/90">
                      {developer.email}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <code className="font-mono text-xs bg-muted text-foreground/90 px-2 py-1 rounded">
                          {truncateId(developer.id)}
                        </code>
                        <Button
                          variant="ghost-faded"
                          size="icon-sm"
                          onClick={() => handleCopyId(developer.id)}
                          title="Copy ID"
                        >
                          {copiedId === developer.id ? (
                            <Check className="h-3 w-3 text-[hsl(var(--success-muted))]" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </Button>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDate(developer.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end">
                        {me?.id !== developer.id && (
                          <Button
                            variant="destructive-outline"
                            size="icon"
                            onClick={() =>
                              setDeleteTarget({
                                id: developer.id,
                                email: developer.email,
                              })
                            }
                            disabled={deleteMutation.isPending}
                            title="Remove team member"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center">
            <Users className="h-12 w-12 text-muted-foreground/60 mx-auto mb-4" />
            <p className="text-muted-foreground mb-2">No team members yet</p>
            <p className="text-sm text-muted-foreground mb-4">
              Invite your first team member to get started
            </p>
            <Button
              variant="outline"
              onClick={() => setIsInviteModalOpen(true)}
            >
              <UserPlus className="h-4 w-4" />
              Invite Member
            </Button>
          </div>
        )}
      </div>

      {/* Invite Dialog */}
      <Dialog
        open={isInviteModalOpen}
        onOpenChange={(open) => {
          setIsInviteModalOpen(open);
          if (!open) setInviteEmail('');
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>
              Send an invitation to join your team
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5 py-4">
            <Label
              htmlFor="invite_email"
              className="text-xs text-foreground/90"
            >
              Email Address
            </Label>
            <Input
              id="invite_email"
              type="email"
              placeholder="colleague@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === 'Enter' &&
                  inviteEmail.trim() &&
                  isValidEmail(inviteEmail.trim())
                ) {
                  handleInvite();
                }
              }}
              className="bg-muted border-border"
            />
            <p className="text-[10px] text-muted-foreground/70">
              They will receive an email with instructions to join
            </p>
          </div>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setIsInviteModalOpen(false);
                setInviteEmail('');
              }}
              disabled={createInvitationMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleInvite}
              disabled={
                createInvitationMutation.isPending ||
                !inviteEmail.trim() ||
                !isValidEmail(inviteEmail.trim())
              }
            >
              {createInvitationMutation.isPending
                ? 'Sending...'
                : 'Send Invitation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Team Member Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Remove Team Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove{' '}
              <span className="font-medium text-foreground/90">
                {deleteTarget?.email}
              </span>{' '}
              from the team? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Removing...' : 'Remove'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revoke Invitation Dialog */}
      <Dialog open={!!revokeTarget} onOpenChange={() => setRevokeTarget(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Revoke Invitation</DialogTitle>
            <DialogDescription>
              Are you sure you want to revoke the invitation for{' '}
              <span className="font-medium text-foreground/90">
                {revokeTarget?.email}
              </span>
              ? They will no longer be able to join.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => setRevokeTarget(null)}
              disabled={revokeInvitationMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRevokeInvitation}
              disabled={revokeInvitationMutation.isPending}
            >
              {revokeInvitationMutation.isPending ? 'Revoking...' : 'Revoke'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
