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
import { pricingTiers } from '@/data/mock/pricing';

export const Route = createFileRoute('/_authenticated/pricing')({
  component: PricingPage,
});

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
      {/* Header */}
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold">Simple, Transparent Pricing</h1>
        <p className="text-xl text-muted-foreground">
          Choose the perfect plan for your health platform
        </p>
      </div>

      {/* Pricing Tiers */}
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
              {/* Limits */}
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

              {/* Features */}
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

      {/* FAQ / Additional Info */}
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
