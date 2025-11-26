import { createFileRoute } from '@tanstack/react-router';
import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const Route = createFileRoute('/_authenticated/pricing')({
  component: PricingPage,
});

interface PricingTier {
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

const pricingTiers: PricingTier[] = [
  {
    id: 'developer',
    name: 'Developer',
    description: 'Perfect for testing and personal projects',
    price: 0,
    billingPeriod: 'month',
    features: [
      'Up to 10 connected users',
      '1,000 API calls/month',
      'Basic health data access',
      'Community support',
      'Public documentation',
    ],
    limits: {
      users: 10,
      apiCalls: 1000,
      automations: 2,
      dataRetention: '30 days',
    },
    cta: 'Get Started Free',
  },
  {
    id: 'starter',
    name: 'Starter',
    description: 'For small teams and early-stage startups',
    price: 49,
    billingPeriod: 'month',
    features: [
      'Up to 100 connected users',
      '10,000 API calls/month',
      'All health data types',
      'Email support',
      '5 automations',
      'Basic analytics',
    ],
    limits: {
      users: 100,
      apiCalls: 10000,
      automations: 5,
      dataRetention: '90 days',
    },
    cta: 'Start Free Trial',
  },
  {
    id: 'professional',
    name: 'Professional',
    description: 'For growing companies with advanced needs',
    price: 199,
    billingPeriod: 'month',
    features: [
      'Up to 1,000 connected users',
      '100,000 API calls/month',
      'All health data types',
      'Priority support',
      'Unlimited automations',
      'Advanced analytics',
      'AI Health Assistant',
      'Custom webhooks',
    ],
    limits: {
      users: 1000,
      apiCalls: 100000,
      automations: 'unlimited',
      dataRetention: '1 year',
    },
    cta: 'Start Free Trial',
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'For large organizations with custom requirements',
    price: 0,
    billingPeriod: 'month',
    features: [
      'Unlimited connected users',
      'Unlimited API calls',
      'All health data types',
      'Dedicated support',
      'Unlimited automations',
      'Custom analytics',
      'AI Health Assistant',
      'Custom integrations',
      'SLA guarantee',
      'HIPAA BAA',
      'SOC 2 compliance',
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

function PricingPage() {
  const handleCTA = (tierId: string) => {
    if (tierId === 'enterprise') {
      // In production, this would open a contact form or redirect to a contact page
      window.location.href =
        'mailto:sales@example.com?subject=Enterprise Plan Inquiry';
    } else {
      // In production, this would redirect to checkout/upgrade flow
      alert(`Upgrading to ${tierId} plan - checkout flow coming soon!`);
    }
  };

  return (
    <div className="p-6 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold">Simple, Transparent Pricing</h1>
        <p className="text-xl text-muted-foreground">
          Choose the perfect plan for your health platform
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl mx-auto">
        {pricingTiers.map((tier) => (
          <Card
            key={tier.id}
            className={`relative flex flex-col ${tier.popular ? 'border-primary shadow-lg scale-105' : ''}`}
          >
            {tier.popular && (
              <div className="absolute -top-3 left-0 right-0 flex justify-center">
                <Badge className="px-3 py-1">Most Popular</Badge>
              </div>
            )}

            <CardHeader>
              <CardTitle className="text-2xl">{tier.name}</CardTitle>
              <CardDescription className="min-h-[40px]">
                {tier.description}
              </CardDescription>
              <div className="mt-4">
                {tier.price === 0 && tier.id !== 'enterprise' ? (
                  <div className="flex items-baseline">
                    <span className="text-4xl font-bold">Free</span>
                  </div>
                ) : tier.id === 'enterprise' ? (
                  <div className="flex items-baseline">
                    <span className="text-4xl font-bold">Custom</span>
                  </div>
                ) : (
                  <div className="flex items-baseline">
                    <span className="text-4xl font-bold">${tier.price}</span>
                    <span className="text-muted-foreground ml-2">
                      /{tier.billingPeriod}
                    </span>
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent className="flex-1">
              <div className="space-y-2 mb-6 pb-6 border-b">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Users</span>
                  <span className="font-medium">
                    {tier.limits.users === 'unlimited'
                      ? 'Unlimited'
                      : tier.limits.users.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">API Calls</span>
                  <span className="font-medium">
                    {tier.limits.apiCalls === 'unlimited'
                      ? 'Unlimited'
                      : tier.limits.apiCalls.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Automations</span>
                  <span className="font-medium">
                    {tier.limits.automations === 'unlimited'
                      ? 'Unlimited'
                      : tier.limits.automations}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Data Retention</span>
                  <span className="font-medium">
                    {tier.limits.dataRetention}
                  </span>
                </div>
              </div>

              <ul className="space-y-3">
                {tier.features.map((feature, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>
            </CardContent>

            <CardFooter>
              <Button
                className="w-full"
                variant={tier.popular ? 'default' : 'outline'}
                onClick={() => handleCTA(tier.id)}
              >
                {tier.cta}
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      <div className="max-w-4xl mx-auto mt-16 space-y-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4">
            Frequently Asked Questions
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                Can I change plans later?
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Yes! You can upgrade or downgrade your plan at any time. Changes
                take effect immediately, and we'll prorate any differences.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                What payment methods do you accept?
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                We accept all major credit cards (Visa, MasterCard, American
                Express) and ACH transfers for annual plans.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Is there a free trial?</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Yes! All paid plans come with a 14-day free trial. No credit
                card required to start. The Developer plan is free forever.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                What about data retention?
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                We store your health data securely for the duration specified in
                your plan. Enterprise customers can request custom retention
                periods.
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="text-center pt-8">
          <h3 className="text-xl font-semibold mb-2">
            Need a custom solution?
          </h3>
          <p className="text-muted-foreground mb-4">
            Contact our sales team to discuss enterprise features, custom
            integrations, and volume pricing.
          </p>
          <Button size="lg" onClick={() => handleCTA('enterprise')}>
            Contact Sales
          </Button>
        </div>
      </div>
    </div>
  );
}
