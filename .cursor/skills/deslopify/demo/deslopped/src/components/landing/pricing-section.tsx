import { AnimatedButton } from "@/components/ui/animated-button"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

const plans = [
  {
    name: "Starter",
    price: "$0",
    period: "during trial",
    description: "For validating your first offer.",
    features: ["Offer builder", "1 landing page", "Launch checklist"],
  },
  {
    name: "Pro",
    price: "$29",
    period: "per month",
    description: "For founders ready to collect payments.",
    features: [
      "Unlimited pages",
      "Custom domain",
      "Payment integration",
      "Email capture",
    ],
    highlighted: true,
  },
]

export function PricingSection() {
  return (
    <section id="pricing" className="border-b border-border py-16 sm:py-20">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="mb-10 max-w-xl space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">Simple pricing</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Start free. Upgrade when you need payments and a custom domain.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className={plan.highlighted ? "ring-2 ring-foreground/20" : undefined}
            >
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>{plan.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <span className="text-3xl font-bold tracking-tight">{plan.price}</span>
                  <span className="ml-2 text-sm text-muted-foreground">{plan.period}</span>
                </div>
                <Separator />
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {plan.features.map((feature) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                {plan.highlighted ? (
                  <AnimatedButton className="h-9 w-full bg-[#2563eb] hover:bg-[#1d4ed8]">
                    Start free trial
                  </AnimatedButton>
                ) : (
                  <Button className="w-full" variant="outline">
                    Get started
                  </Button>
                )}
              </CardFooter>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
