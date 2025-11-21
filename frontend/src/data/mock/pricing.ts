export interface PricingTier {
  id: string;
  name: string;
  description: string;
  price: number;
  billingPeriod: 'month' | 'year';
  features: string[];
  limits: {
    users: number | 'unlimited';
    apiCalls: number | 'unlimited';
    automations: number | 'unlimited';
    dataRetention: string;
  };
  cta: string;
  popular?: boolean;
}

export const pricingTiers: PricingTier[] = [
  {
    id: 'free',
    name: 'Developer',
    description: 'Perfect for testing and development',
    price: 0,
    billingPeriod: 'month',
    features: [
      'Up to 100 users',
      '10,000 API calls/month',
      '5 automations',
      'Basic health data sync',
      'Community support',
      '30 days data retention',
    ],
    limits: {
      users: 100,
      apiCalls: 10000,
      automations: 5,
      dataRetention: '30 days',
    },
    cta: 'Get Started',
  },
  {
    id: 'starter',
    name: 'Starter',
    description: 'For small teams and growing apps',
    price: 49,
    billingPeriod: 'month',
    features: [
      'Up to 1,000 users',
      '100,000 API calls/month',
      '25 automations',
      'All health data types',
      'Email support',
      '90 days data retention',
      'Widget embedding',
      'AI health insights',
    ],
    limits: {
      users: 1000,
      apiCalls: 100000,
      automations: 25,
      dataRetention: '90 days',
    },
    cta: 'Start Free Trial',
  },
  {
    id: 'professional',
    name: 'Professional',
    description: 'For production apps with serious users',
    price: 199,
    billingPeriod: 'month',
    popular: true,
    features: [
      'Up to 10,000 users',
      '1,000,000 API calls/month',
      'Unlimited automations',
      'All health data types',
      'Priority support',
      '1 year data retention',
      'Widget embedding',
      'AI health insights',
      'Advanced analytics',
      'Custom webhooks',
      'SSO integration',
    ],
    limits: {
      users: 10000,
      apiCalls: 1000000,
      automations: 'unlimited',
      dataRetention: '1 year',
    },
    cta: 'Start Free Trial',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'For large-scale deployments',
    price: 0,
    billingPeriod: 'month',
    features: [
      'Unlimited users',
      'Unlimited API calls',
      'Unlimited automations',
      'All health data types',
      'Dedicated support',
      'Custom data retention',
      'Widget embedding',
      'AI health insights',
      'Advanced analytics',
      'Custom webhooks',
      'SSO integration',
      'Custom integrations',
      'SLA guarantee',
      'On-premise deployment',
    ],
    limits: {
      users: 'unlimited',
      apiCalls: 'unlimited',
      automations: 'unlimited',
      dataRetention: 'Custom',
    },
    cta: 'Contact Sales',
  },
];
