import type {
  HeartRateData,
  SleepData,
  ActivityData,
  HealthDataSummary,
} from '@/lib/api/types';

// Generate heart rate data for the last 7 days
export const generateHeartRateData = (userId: string): HeartRateData[] => {
  const data: HeartRateData[] = [];
  const now = new Date();

  for (let day = 6; day >= 0; day--) {
    const date = new Date(now);
    date.setDate(date.getDate() - day);
    const dateStr = date.toISOString().split('T')[0];

    // Generate 24 hourly readings
    for (let hour = 0; hour < 24; hour++) {
      const timestamp = new Date(date);
      timestamp.setHours(hour, 0, 0, 0);

      // Simulate realistic heart rate patterns
      let baseRate = 65;
      if (hour >= 6 && hour <= 9) baseRate = 75; // Morning
      if (hour >= 12 && hour <= 14) baseRate = 80; // Midday
      if (hour >= 17 && hour <= 20) baseRate = 85; // Evening activity
      if (hour >= 22 || hour <= 5) baseRate = 55; // Sleep

      const variation = Math.floor(Math.random() * 15) - 7;

      data.push({
        id: `hr-${userId}-${dateStr}-${hour}`,
        userId,
        timestamp: timestamp.toISOString(),
        value: baseRate + variation,
        source: hour % 3 === 0 ? 'garmin' : 'fitbit',
      });
    }
  }

  return data;
};

// Generate sleep data for the last 7 nights
export const generateSleepData = (userId: string): SleepData[] => {
  const data: SleepData[] = [];
  const now = new Date();

  for (let day = 6; day >= 0; day--) {
    const date = new Date(now);
    date.setDate(date.getDate() - day);
    const dateStr = date.toISOString().split('T')[0];

    const sleepStart = new Date(date);
    sleepStart.setHours(22, 30, 0, 0);

    const sleepEnd = new Date(date);
    sleepEnd.setDate(sleepEnd.getDate() + 1);
    sleepEnd.setHours(6, 45, 0, 0);

    const totalMinutes = 495 + Math.floor(Math.random() * 60) - 30;
    const deepMinutes = Math.floor(totalMinutes * (0.15 + Math.random() * 0.1));
    const remMinutes = Math.floor(totalMinutes * (0.2 + Math.random() * 0.1));
    const lightMinutes = totalMinutes - deepMinutes - remMinutes;

    const efficiency = 70 + Math.floor(Math.random() * 25);

    data.push({
      id: `sleep-${userId}-${dateStr}`,
      userId,
      date: dateStr,
      startTime: sleepStart.toISOString(),
      endTime: sleepEnd.toISOString(),
      totalMinutes,
      deepMinutes,
      lightMinutes,
      remMinutes,
      awakeMinutes: Math.floor(totalMinutes * 0.05),
      efficiency,
      quality:
        efficiency >= 85
          ? 'excellent'
          : efficiency >= 70
            ? 'good'
            : efficiency >= 60
              ? 'fair'
              : 'poor',
      source: day % 2 === 0 ? 'garmin' : 'fitbit',
    });
  }

  return data;
};

// Generate activity data for the last 7 days
export const generateActivityData = (userId: string): ActivityData[] => {
  const data: ActivityData[] = [];
  const now = new Date();

  for (let day = 6; day >= 0; day--) {
    const date = new Date(now);
    date.setDate(date.getDate() - day);
    const dateStr = date.toISOString().split('T')[0];

    const steps = 5000 + Math.floor(Math.random() * 8000);
    const activeMinutes = 30 + Math.floor(Math.random() * 90);
    const calories = 1800 + Math.floor(Math.random() * 800);

    data.push({
      id: `activity-${userId}-${dateStr}`,
      userId,
      date: dateStr,
      steps,
      activeMinutes,
      calories,
      distance: steps * 0.0007, // km
      floors: Math.floor(Math.random() * 15),
      source: day % 2 === 0 ? 'garmin' : 'fitbit',
    });
  }

  return data;
};

// Health data summary for a user
export const generateHealthSummary = (userId: string): HealthDataSummary => {
  const heartRate = generateHeartRateData(userId);
  const sleep = generateSleepData(userId);
  const activity = generateActivityData(userId);

  const avgHeartRate = Math.floor(
    heartRate.reduce((sum, hr) => sum + hr.value, 0) / heartRate.length
  );

  const avgSleepMinutes = Math.floor(
    sleep.reduce((sum, s) => sum + s.totalMinutes, 0) / sleep.length
  );

  const avgSteps = Math.floor(
    activity.reduce((sum, a) => sum + a.steps, 0) / activity.length
  );

  return {
    userId,
    period: '7d',
    heartRate: {
      average: avgHeartRate,
      min: Math.min(...heartRate.map((hr) => hr.value)),
      max: Math.max(...heartRate.map((hr) => hr.value)),
      data: heartRate,
    },
    sleep: {
      averageMinutes: avgSleepMinutes,
      averageEfficiency: Math.floor(
        sleep.reduce((sum, s) => sum + s.efficiency, 0) / sleep.length
      ),
      data: sleep,
    },
    activity: {
      averageSteps: avgSteps,
      totalActiveMinutes: activity.reduce((sum, a) => sum + a.activeMinutes, 0),
      data: activity,
    },
    lastUpdated: new Date().toISOString(),
  };
};
