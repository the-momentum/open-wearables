import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import {
  Plus,
  PlayCircle,
  Trash2,
  Power,
  PowerOff,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  useAutomations,
  useCreateAutomation,
  useDeleteAutomation,
  useToggleAutomation,
  useTestAutomation,
  useAutomationTriggers,
  useImproveDescription,
} from '@/hooks/api/use-automations';
import { LoadingState } from '@/components/common/loading-spinner';
import { ErrorState } from '@/components/common/error-state';
import type { AutomationCreate } from '@/lib/api/types';
import { toast } from 'sonner';

export const Route = createFileRoute('/_authenticated/health-insights')({
  component: HealthInsightsPage,
});

function HealthInsightsPage() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedAutomationId, setSelectedAutomationId] = useState<
    string | null
  >(null);
  const [showTriggers, setShowTriggers] = useState(false);
  const [formData, setFormData] = useState<AutomationCreate>({
    name: '',
    description: '',
    webhookUrl: '',
    isEnabled: true,
  });

  const { data: automations, isLoading, error } = useAutomations();
  const createMutation = useCreateAutomation();
  const deleteMutation = useDeleteAutomation();
  const toggleMutation = useToggleAutomation();
  const testMutation = useTestAutomation();
  const improveMutation = useImproveDescription();

  const { data: triggers } = useAutomationTriggers(selectedAutomationId || '');

  const handleCreate = async () => {
    if (!formData.name || !formData.description || !formData.webhookUrl) {
      toast.error('Please fill in all fields');
      return;
    }

    await createMutation.mutateAsync(formData);
    setIsCreateDialogOpen(false);
    setFormData({
      name: '',
      description: '',
      webhookUrl: '',
      isEnabled: true,
    });
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this automation?')) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const handleToggle = async (id: string, currentState: boolean) => {
    await toggleMutation.mutateAsync({ id, isEnabled: !currentState });
  };

  const handleTest = async (id: string) => {
    const result = await testMutation.mutateAsync(id);
    toast.success(`Test completed: ${result.totalTriggers} triggers found`);
    setSelectedAutomationId(id);
    setShowTriggers(true);
  };

  const handleImproveDescription = async () => {
    if (!formData.description) {
      toast.error('Please enter a description first');
      return;
    }

    const result = await improveMutation.mutateAsync(formData.description);
    setFormData((prev) => ({
      ...prev,
      description: result.improvedDescription,
    }));
    toast.success('Description improved with AI');
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  if (isLoading) {
    return <LoadingState message="Loading automations..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load automations" />;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Health Insights Automations</h1>
          <p className="text-muted-foreground mt-1">
            Automate webhooks based on health data patterns
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Automation
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Active Automations</CardTitle>
          <CardDescription>
            Manage your health data automations and webhooks
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Triggers</TableHead>
                <TableHead>Last Triggered</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {automations && automations.length > 0 ? (
                automations.map((automation) => (
                  <TableRow key={automation.id}>
                    <TableCell className="font-medium">
                      {automation.name}
                    </TableCell>
                    <TableCell className="max-w-md truncate">
                      {automation.description}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={automation.isEnabled ? 'default' : 'secondary'}
                      >
                        {automation.isEnabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </TableCell>
                    <TableCell>{automation.triggerCount}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(automation.lastTriggered)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            handleToggle(automation.id, automation.isEnabled)
                          }
                          disabled={toggleMutation.isPending}
                        >
                          {automation.isEnabled ? (
                            <PowerOff className="h-4 w-4" />
                          ) : (
                            <Power className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTest(automation.id)}
                          disabled={testMutation.isPending}
                        >
                          <PlayCircle className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(automation.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center py-8 text-muted-foreground"
                  >
                    No automations yet. Create your first automation to get
                    started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create New Automation</DialogTitle>
            <DialogDescription>
              Set up a webhook automation based on health data patterns
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Automation Name</Label>
              <Input
                id="name"
                placeholder="e.g., High Heart Rate Alert"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label htmlFor="description">Description</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleImproveDescription}
                  disabled={improveMutation.isPending || !formData.description}
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  {improveMutation.isPending
                    ? 'Improving...'
                    : 'Improve with AI'}
                </Button>
              </div>
              <Textarea
                id="description"
                placeholder="Describe when this automation should trigger..."
                rows={4}
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
              />
              <p className="text-xs text-muted-foreground">
                Describe the conditions that should trigger this webhook
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhookUrl">Webhook URL</Label>
              <Input
                id="webhookUrl"
                type="url"
                placeholder="https://api.example.com/webhooks/health-alert"
                value={formData.webhookUrl}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    webhookUrl: e.target.value,
                  }))
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Automation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Trigger History Dialog */}
      <Dialog open={showTriggers} onOpenChange={setShowTriggers}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Test Results & Trigger History</DialogTitle>
            <DialogDescription>
              Recent triggers for this automation (last 24 hours simulation)
            </DialogDescription>
          </DialogHeader>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Triggered At</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {triggers && triggers.length > 0 ? (
                triggers.map((trigger) => (
                  <TableRow key={trigger.id}>
                    <TableCell>{trigger.userName}</TableCell>
                    <TableCell>{trigger.userEmail}</TableCell>
                    <TableCell>{formatDate(trigger.triggeredAt)}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          trigger.webhookStatus === 'success'
                            ? 'default'
                            : 'destructive'
                        }
                      >
                        {trigger.webhookStatus}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-center py-8 text-muted-foreground"
                  >
                    No triggers found in the test period
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </DialogContent>
      </Dialog>
    </div>
  );
}
