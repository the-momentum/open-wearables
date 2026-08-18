import { useState } from 'react';
import {
  Plus,
  Copy,
  Trash2,
  Smartphone,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  useApplications,
  useCreateApplication,
  useDeleteApplication,
  useRotateApplicationSecret,
} from '@/hooks/api/use-applications';
import type { Application, ApplicationWithSecret } from '@/lib/api/types';
import { copyToClipboard } from '@/lib/utils/clipboard';
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

export function ApplicationsSection() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [appName, setAppName] = useState('');
  const [revealedCredentials, setRevealedCredentials] =
    useState<ApplicationWithSecret | null>(null);
  const [secretRevealTitle, setSecretRevealTitle] = useState(
    'Application Created'
  );
  const [appToDelete, setAppToDelete] = useState<Application | null>(null);
  const [appToRotate, setAppToRotate] = useState<Application | null>(null);

  const { data: applications, isLoading, error, refetch } = useApplications();
  const createMutation = useCreateApplication();
  const deleteMutation = useDeleteApplication();
  const rotateMutation = useRotateApplicationSecret();

  const handleCreate = async () => {
    if (!appName.trim()) {
      toast.error('Please enter an application name');
      return;
    }

    const created = await createMutation.mutateAsync({
      name: appName.trim(),
    });
    setIsCreateDialogOpen(false);
    setAppName('');
    setSecretRevealTitle('Application Created');
    setRevealedCredentials(created);
  };

  const handleDeleteConfirm = async () => {
    if (!appToDelete) return;
    await deleteMutation.mutateAsync(appToDelete.app_id);
    setAppToDelete(null);
  };

  const handleRotateConfirm = async () => {
    if (!appToRotate) return;
    const rotated = await rotateMutation.mutateAsync(appToRotate.app_id);
    setAppToRotate(null);
    setSecretRevealTitle('Secret Rotated');
    setRevealedCredentials(rotated);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-muted rounded-md w-full" />
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 bg-muted/50 rounded-md" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12 text-center">
        <p className="text-muted-foreground mb-4">
          Failed to load applications
        </p>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border/60 flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-medium text-foreground">
              SDK Applications
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Credentials for mobile apps that push health data via the SDK. Use{' '}
              <code className="text-[10px]">app_id</code> and{' '}
              <code className="text-[10px]">app_secret</code> on your backend
              only.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => setIsCreateDialogOpen(true)}
            className="shrink-0"
          >
            <Plus className="h-4 w-4" />
            Create Application
          </Button>
        </div>

        {applications && applications.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/60 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    App ID
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {applications.map((app) => (
                  <tr
                    key={app.id}
                    className="hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-medium text-foreground/90">
                      {app.name}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <code className="font-mono text-xs bg-muted text-foreground/90 px-2 py-1 rounded">
                          {app.app_id}
                        </code>
                        <Button
                          variant="ghost-faded"
                          size="icon-sm"
                          aria-label="Copy app ID"
                          onClick={() =>
                            copyToClipboard(app.app_id, 'App ID copied')
                          }
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDate(app.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          aria-label="Rotate application secret"
                          onClick={() => setAppToRotate(app)}
                          disabled={rotateMutation.isPending}
                        >
                          <RefreshCw className="h-4 w-4" aria-hidden />
                        </Button>
                        <Button
                          variant="destructive-outline"
                          size="icon"
                          aria-label="Delete application"
                          onClick={() => setAppToDelete(app)}
                          disabled={deleteMutation.isPending}
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
            <Smartphone className="h-12 w-12 text-muted-foreground/60 mx-auto mb-4" />
            <p className="text-muted-foreground mb-2">No applications yet</p>
            <p className="text-sm text-muted-foreground mb-4">
              Create an application to authenticate your mobile SDK
            </p>
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(true)}
              aria-label="Create application"
            >
              <Plus className="h-4 w-4" />
              Create Application
            </Button>
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create Application</DialogTitle>
            <DialogDescription>
              Register a mobile app to get SDK credentials (
              <code className="text-xs">app_id</code> /{' '}
              <code className="text-xs">app_secret</code>)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="app_name" className="text-foreground/90">
              Application Name
            </Label>
            <Input
              id="app_name"
              type="text"
              placeholder="e.g., My iOS App"
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void handleCreate();
                }
              }}
              className="bg-muted border-border"
            />
            <p className="text-[10px] text-muted-foreground/70">
              A descriptive name to identify this app
            </p>
          </div>
          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateDialogOpen(false);
                setAppName('');
              }}
              aria-label="Cancel create"
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={createMutation.isPending}
              aria-label="Create application"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Application'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* One-time secret reveal */}
      <Dialog
        open={revealedCredentials !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRevealedCredentials(null);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{secretRevealTitle}</DialogTitle>
            <DialogDescription>
              Store these credentials in your backend environment. The app
              secret is shown only once and cannot be retrieved again.
            </DialogDescription>
          </DialogHeader>

          {revealedCredentials && (
            <div className="space-y-4">
              <div className="flex items-start gap-2 rounded-lg border border-[hsl(var(--warning-muted)/0.3)] bg-[hsl(var(--warning-muted)/0.1)] p-3 text-sm text-[hsl(var(--warning-muted))]">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <p>
                  Copy the secret now. If you lose it, you will need to rotate
                  and update your backend.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label className="text-foreground/90">App ID</Label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 font-mono text-xs bg-muted text-foreground/90 px-3 py-2 rounded break-all">
                    {revealedCredentials.app_id}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label="Copy app ID"
                    onClick={() =>
                      copyToClipboard(
                        revealedCredentials.app_id,
                        'App ID copied'
                      )
                    }
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-foreground/90">App Secret</Label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 font-mono text-xs bg-muted text-foreground/90 px-3 py-2 rounded break-all">
                    {revealedCredentials.app_secret}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label="Copy app secret"
                    onClick={() =>
                      copyToClipboard(
                        revealedCredentials.app_secret,
                        'App secret copied'
                      )
                    }
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              onClick={() => setRevealedCredentials(null)}
              aria-label="Cancel secret reveal"
            >
              I&apos;ve saved the secret
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={appToDelete !== null}
        onOpenChange={(open) => {
          if (!open) setAppToDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Application</AlertDialogTitle>
            <AlertDialogDescription>
              {appToDelete
                ? `Are you sure you want to delete "${appToDelete.name}"? Mobile apps using these credentials will stop working. This cannot be undone.`
                : 'Are you sure you want to delete this application? This cannot be undone.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
              aria-label="Delete application"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={appToRotate !== null}
        onOpenChange={(open) => {
          if (!open) setAppToRotate(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rotate Application Secret</AlertDialogTitle>
            <AlertDialogDescription>
              {appToRotate
                ? `Rotate the secret for "${appToRotate.name}"? The current secret will stop working immediately.`
                : 'Rotate this application secret? The current secret will stop working immediately.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={rotateMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRotateConfirm}
              disabled={rotateMutation.isPending}
              aria-label="Rotate application secret"
            >
              {rotateMutation.isPending ? 'Rotating...' : 'Rotate Secret'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
