import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import {
  Plus,
  PlayCircle,
  Trash2,
  Power,
  PowerOff,
  Sparkles,
  Zap,
} from 'lucide-react';
import {
  useAutomations,
  useCreateAutomation,
  useDeleteAutomation,
  useToggleAutomation,
  useTestAutomation,
  useAutomationTriggers,
  useImproveDescription,
} from '@/hooks/api/use-automations';
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

  const { data: automations, isLoading, error, refetch } = useAutomations();
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
    return (
      <div className="p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-medium text-white">
            Health Insights Automations
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Automate webhooks based on health data patterns
          </p>
        </div>
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
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
          <p className="text-zinc-400 mb-4">Failed to load automations</p>
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
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-white">
            Health Insights Automations
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Automate webhooks based on health data patterns
          </p>
        </div>
        <button
          onClick={() => setIsCreateDialogOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Create Automation
        </button>
      </div>

      {/* Automations Table */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-white">Active Automations</h2>
          <p className="text-xs text-zinc-500 mt-1">
            Manage your health data automations and webhooks
          </p>
        </div>

        {automations && automations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Description
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Triggers
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Last Triggered
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {automations.map((automation) => (
                  <tr
                    key={automation.id}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-medium text-zinc-300">
                      {automation.name}
                    </td>
                    <td className="px-6 py-4 text-sm text-zinc-400 max-w-md truncate">
                      {automation.description}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          automation.isEnabled
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-zinc-700 text-zinc-400'
                        }`}
                      >
                        {automation.isEnabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-zinc-400">
                      {automation.triggerCount}
                    </td>
                    <td className="px-6 py-4 text-xs text-zinc-500">
                      {formatDate(automation.lastTriggered)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() =>
                            handleToggle(automation.id, automation.isEnabled)
                          }
                          disabled={toggleMutation.isPending}
                          className="p-2 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-md transition-colors disabled:opacity-50"
                        >
                          {automation.isEnabled ? (
                            <PowerOff className="h-4 w-4" />
                          ) : (
                            <Power className="h-4 w-4" />
                          )}
                        </button>
                        <button
                          onClick={() => handleTest(automation.id)}
                          disabled={testMutation.isPending}
                          className="p-2 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-md transition-colors disabled:opacity-50"
                        >
                          <PlayCircle className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(automation.id)}
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
            <Zap className="h-12 w-12 text-zinc-700 mx-auto mb-4" />
            <p className="text-zinc-400 mb-2">No automations yet</p>
            <p className="text-sm text-zinc-500 mb-4">
              Create your first automation to get started
            </p>
            <button
              onClick={() => setIsCreateDialogOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Create Automation
            </button>
          </div>
        )}
      </div>

      {/* Create Dialog */}
      {isCreateDialogOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-2xl shadow-2xl">
            <div className="p-6 border-b border-zinc-800">
              <h2 className="text-lg font-medium text-white">
                Create New Automation
              </h2>
              <p className="text-sm text-zinc-500 mt-1">
                Set up a webhook automation based on health data patterns
              </p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Automation Name
                </label>
                <input
                  type="text"
                  placeholder="e.g., High Heart Rate Alert"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, name: e.target.value }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium text-zinc-300">
                    Description
                  </label>
                  <button
                    type="button"
                    onClick={handleImproveDescription}
                    disabled={improveMutation.isPending || !formData.description}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 border border-zinc-700 rounded-md hover:text-white hover:border-zinc-600 transition-colors disabled:opacity-50"
                  >
                    <Sparkles className="h-3 w-3" />
                    {improveMutation.isPending ? 'Improving...' : 'Improve with AI'}
                  </button>
                </div>
                <textarea
                  placeholder="Describe when this automation should trigger..."
                  rows={4}
                  value={formData.description}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all resize-none"
                />
                <p className="text-[10px] text-zinc-600">
                  Describe the conditions that should trigger this webhook
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Webhook URL
                </label>
                <input
                  type="url"
                  placeholder="https://api.example.com/webhooks/health-alert"
                  value={formData.webhookUrl}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      webhookUrl: e.target.value,
                    }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 focus:border-zinc-600 transition-all"
                />
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3">
              <button
                onClick={() => setIsCreateDialogOpen(false)}
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
                {createMutation.isPending ? 'Creating...' : 'Create Automation'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Triggers Dialog */}
      {showTriggers && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-4xl max-h-[80vh] overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-zinc-800">
              <h2 className="text-lg font-medium text-white">
                Test Results & Trigger History
              </h2>
              <p className="text-sm text-zinc-500 mt-1">
                Recent triggers for this automation (last 24 hours simulation)
              </p>
            </div>
            <div className="overflow-x-auto max-h-[60vh] overflow-y-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-zinc-900">
                  <tr className="border-b border-zinc-800 text-left">
                    <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Triggered At
                    </th>
                    <th className="px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {triggers && triggers.length > 0 ? (
                    triggers.map((trigger) => (
                      <tr
                        key={trigger.id}
                        className="hover:bg-zinc-800/30 transition-colors"
                      >
                        <td className="px-6 py-4 text-sm text-zinc-300">
                          {trigger.userName}
                        </td>
                        <td className="px-6 py-4 text-sm text-zinc-400">
                          {trigger.userEmail}
                        </td>
                        <td className="px-6 py-4 text-xs text-zinc-500">
                          {formatDate(trigger.triggeredAt)}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-2 py-0.5 text-xs rounded-full ${
                              trigger.webhookStatus === 'success'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-red-500/20 text-red-400'
                            }`}
                          >
                            {trigger.webhookStatus}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-6 py-12 text-center text-zinc-500"
                      >
                        No triggers found in the test period
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setShowTriggers(false)}
                className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
