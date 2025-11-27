import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Heart, TrendingUp, TrendingDown, Activity } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { HeartRateListResponse } from '@/lib/api/types';
import { format } from 'date-fns';

interface HeartRateChartProps {
  data: HeartRateListResponse;
  isLoading?: boolean;
}

export function HeartRateChart({ data, isLoading }: HeartRateChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Heart className="h-5 w-5 text-red-500" />
            Heart Rate
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 flex items-center justify-center text-muted-foreground">
            Loading heart rate data...
          </div>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.data.map((item) => ({
    date: format(new Date(item.date), 'MMM dd'),
    avg: item.avg?.value ?? null,
    min: item.min?.value ?? null,
    max: item.max?.value ?? null,
  }));

  const { summary } = data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Average HR</p>
                <p className="text-2xl font-bold">
                  {summary.avg_heart_rate.toFixed(0)} bpm
                </p>
              </div>
              <Activity className="h-8 w-8 text-red-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Max HR</p>
                <p className="text-2xl font-bold">
                  {summary.max_heart_rate.toFixed(0)} bpm
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-orange-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Min HR</p>
                <p className="text-2xl font-bold">
                  {summary.min_heart_rate.toFixed(0)} bpm
                </p>
              </div>
              <TrendingDown className="h-8 w-8 text-green-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Heart className="h-5 w-5 text-red-500" />
            Heart Rate Trend
          </CardTitle>
        </CardHeader>
        <CardContent>
          {chartData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No heart rate data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-50" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 12 }}
                  label={{
                    value: 'BPM',
                    angle: -90,
                    position: 'insideLeft',
                    style: { textAnchor: 'middle' },
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avg"
                  stroke="#ef4444"
                  name="Average"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="max"
                  stroke="#f97316"
                  name="Max"
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="min"
                  stroke="#22c55e"
                  name="Min"
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
