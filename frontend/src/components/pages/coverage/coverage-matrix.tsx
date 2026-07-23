import { useState } from 'react';
import { SourceBadge } from '@/components/common/source-badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { CoverageResponse, TimeseriesCategory } from '@/lib/api';

interface MatrixProps {
  providers: string[];
  rows: { code: string; unit?: string; supportedBy: string[] }[];
}

function Matrix({ providers, rows }: MatrixProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-zinc-500 py-4">No data for this layer.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="sticky left-0 bg-zinc-950 px-3 py-2.5 text-left text-xs font-medium text-zinc-500 w-56 border-b border-zinc-800" />
            {providers.map((p) => (
              <th
                key={p}
                className="px-2 py-2.5 text-center min-w-[72px] border-b border-zinc-800"
              >
                <SourceBadge provider={p} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.code} className={i % 2 === 0 ? 'bg-zinc-900/20' : 'bg-transparent'}>
              <td className="sticky left-0 bg-inherit px-3 py-2 border-b border-zinc-800/40">
                <div className="flex items-baseline gap-2">
                  <code className="text-xs text-zinc-300 font-mono">{row.code}</code>
                  {row.unit && (
                    <span className="text-[10px] text-zinc-400 bg-zinc-800 px-1 py-0.5 rounded">
                      {row.unit}
                    </span>
                  )}
                </div>
              </td>
              {providers.map((p) => {
                const supported = row.supportedBy.includes(p);
                return (
                  <td key={p} className="px-2 py-2 text-center border-b border-zinc-800/40">
                    <span className="sr-only">
                      {supported ? 'Supported' : 'Not supported'}
                    </span>
                    <span
                      aria-hidden="true"
                      className={
                        supported
                          ? 'inline-flex h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20'
                          : 'inline-flex h-2 w-2 rounded-full bg-zinc-800'
                      }
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TimeseriesTab({
  providers,
  categories,
}: {
  providers: string[];
  categories: TimeseriesCategory[];
}) {
  const [activeCategory, setActiveCategory] = useState(categories[0]?.name ?? '');

  if (categories.length === 0) {
    return <p className="text-sm text-zinc-500 py-4">No timeseries data.</p>;
  }

  // Guard against a stale selection if the category list changes.
  const active = categories.some((c) => c.name === activeCategory)
    ? activeCategory
    : categories[0].name;

  return (
    <Tabs value={active} onValueChange={setActiveCategory} className="space-y-4">
      <TabsList className="flex-wrap h-auto gap-1 bg-zinc-900/60 p-1">
        {categories.map((cat) => (
          <TabsTrigger key={cat.name} value={cat.name} className="text-xs">
            {cat.name}
          </TabsTrigger>
        ))}
      </TabsList>
      {categories.map((cat) => (
        <TabsContent key={cat.name} value={cat.name}>
          <Matrix
            providers={providers}
            rows={cat.metrics.map((m) => ({
              code: m.code,
              unit: m.unit,
              supportedBy: m.providers,
            }))}
          />
        </TabsContent>
      ))}
    </Tabs>
  );
}

interface Props {
  data: CoverageResponse;
}

export function CoverageMatrix({ data }: Props) {
  const { providers, timeseries, workout_fields, sleep_fields, menstrual_cycle_fields, health_scores } =
    data;
  const [activeTab, setActiveTab] = useState('timeseries');

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
      <TabsList className="bg-zinc-900/60 border border-zinc-800 p-1 h-auto">
        <TabsTrigger value="timeseries" className="text-sm">Timeseries</TabsTrigger>
        <TabsTrigger value="workout" className="text-sm">Workout</TabsTrigger>
        <TabsTrigger value="sleep" className="text-sm">Sleep</TabsTrigger>
        <TabsTrigger value="womens-health" className="text-sm">Women's Health</TabsTrigger>
        <TabsTrigger value="scores" className="text-sm">Health Scores</TabsTrigger>
      </TabsList>

      <TabsContent value="timeseries">
        <TimeseriesTab providers={providers} categories={timeseries} />
      </TabsContent>

      <TabsContent value="workout">
        <Matrix
          providers={providers}
          rows={workout_fields.map((f) => ({ code: f.code, supportedBy: f.providers }))}
        />
      </TabsContent>

      <TabsContent value="sleep">
        <Matrix
          providers={providers}
          rows={sleep_fields.map((f) => ({ code: f.code, supportedBy: f.providers }))}
        />
      </TabsContent>

      <TabsContent value="womens-health">
        <Matrix
          providers={providers}
          rows={menstrual_cycle_fields.map((f) => ({ code: f.code, supportedBy: f.providers }))}
        />
      </TabsContent>

      <TabsContent value="scores">
        <Matrix
          providers={providers}
          rows={health_scores.map((s) => ({ code: s.code, supportedBy: s.providers }))}
        />
      </TabsContent>
    </Tabs>
  );
}
