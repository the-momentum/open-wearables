import { createFileRoute } from '@tanstack/react-router';
import { Check } from 'lucide-react';

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
      window.location.href =
        'mailto:sales@example.com?subject=Enterprise Plan Inquiry';
    } else {
      alert(`Upgrading to ${tierId} plan - checkout flow coming soon!`);
    }
  };

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-medium text-white">
          Simple, Transparent Pricing
        </h1>
        <p className="text-zinc-500 mt-2">
          Choose the perfect plan for your health platform
        </p>
      </div>

      {/* Pricing Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl mx-auto">
        {pricingTiers.map((tier) => (
          <div
            key={tier.id}
            className={`relative flex flex-col bg-zinc-900/50 border rounded-xl overflow-hidden transition-all ${
              tier.popular
                ? 'border-white shadow-[0_0_30px_-5px_rgba(255,255,255,0.15)] scale-[1.02]'
                : 'border-zinc-800 hover:border-zinc-700'
            }`}
          >
            {tier.popular && (
              <div className="absolute -top-px left-0 right-0 h-1 bg-white" />
            )}

            {/* Header */}
            <div className="p-6 border-b border-zinc-800">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-white">{tier.name}</h3>
                {tier.popular && (
                  <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider font-medium bg-white text-black rounded-full">
                    Popular
                  </span>
                )}
              </div>
              <p className="text-sm text-zinc-500 mt-1 min-h-[40px]">
                {tier.description}
              </p>
              <div className="mt-4">
                {tier.price === 0 && tier.id !== 'enterprise' ? (
                  <div className="flex items-baseline">
                    <span className="text-3xl font-medium text-white">Free</span>
                  </div>
                ) : tier.id === 'enterprise' ? (
                  <div className="flex items-baseline">
                    <span className="text-3xl font-medium text-white">
                      Custom
                    </span>
                  </div>
                ) : (
                  <div className="flex items-baseline">
                    <span className="text-3xl font-medium text-white">
                      ${tier.price}
                    </span>
                    <span className="text-zinc-500 ml-1">
                      /{tier.billingPeriod}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Limits */}
            <div className="p-6 border-b border-zinc-800 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">Users</span>
                <span className="text-zinc-300">
                  {tier.limits.users === 'unlimited'
                    ? 'Unlimited'
                    : tier.limits.users.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">API Calls</span>
                <span className="text-zinc-300">
                  {tier.limits.apiCalls === 'unlimited'
                    ? 'Unlimited'
                    : tier.limits.apiCalls.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">Automations</span>
                <span className="text-zinc-300">
                  {tier.limits.automations === 'unlimited'
                    ? 'Unlimited'
                    : tier.limits.automations}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">Data Retention</span>
                <span className="text-zinc-300">{tier.limits.dataRetention}</span>
              </div>
            </div>

            {/* Features */}
            <div className="flex-1 p-6">
              <ul className="space-y-3">
                {tier.features.map((feature, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <Check className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-zinc-400">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* CTA */}
            <div className="p-6 pt-0">
              <button
                onClick={() => handleCTA(tier.id)}
                className={`w-full py-2.5 rounded-md text-sm font-medium transition-colors ${
                  tier.popular
                    ? 'bg-white text-black hover:bg-zinc-200'
                    : 'bg-zinc-800 text-white hover:bg-zinc-700 border border-zinc-700'
                }`}
              >
                {tier.cta}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* FAQ Section */}
      <div className="max-w-4xl mx-auto mt-16 space-y-8">
        <div className="text-center">
          <h2 className="text-xl font-medium text-white">
            Frequently Asked Questions
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
            <h3 className="text-sm font-medium text-white mb-2">
              Can I change plans later?
            </h3>
            <p className="text-sm text-zinc-500">
              Yes! You can upgrade or downgrade your plan at any time. Changes
              take effect immediately, and we'll prorate any differences.
            </p>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
            <h3 className="text-sm font-medium text-white mb-2">
              What payment methods do you accept?
            </h3>
            <p className="text-sm text-zinc-500">
              We accept all major credit cards (Visa, MasterCard, American
              Express) and ACH transfers for annual plans.
            </p>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
            <h3 className="text-sm font-medium text-white mb-2">
              Is there a free trial?
            </h3>
            <p className="text-sm text-zinc-500">
              Yes! All paid plans come with a 14-day free trial. No credit card
              required to start. The Developer plan is free forever.
            </p>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
            <h3 className="text-sm font-medium text-white mb-2">
              What about data retention?
            </h3>
            <p className="text-sm text-zinc-500">
              We store your health data securely for the duration specified in
              your plan. Enterprise customers can request custom retention
              periods.
            </p>
          </div>
        </div>

        <div className="text-center pt-8">
          <h3 className="text-lg font-medium text-white mb-2">
            Need a custom solution?
          </h3>
          <p className="text-zinc-500 mb-4">
            Contact our sales team to discuss enterprise features, custom
            integrations, and volume pricing.
          </p>
          <button
            onClick={() => handleCTA('enterprise')}
            className="px-6 py-2.5 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
          >
            Contact Sales
          </button>
        </div>
      </div>
    </div>
  );
}
