"use client"

import type { ReactNode } from "react"
import { FileText, LayoutTemplate, CheckSquare, Layers } from "lucide-react"

import { BentoGridShowcase } from "@/components/bento-grid"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

function BentoCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
        <CardDescription className="leading-relaxed">{description}</CardDescription>
      </CardHeader>
      {children && <CardContent>{children}</CardContent>}
    </Card>
  )
}

function MediaPlaceholder() {
  return (
    <div className="flex h-28 items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 text-xs text-muted-foreground">
      Screenshot placeholder
    </div>
  )
}

export function FeaturesSection() {
  return (
    <section className="border-b border-border py-16 sm:py-20">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="mb-10 max-w-xl space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">
            Everything you need to ship
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Three focused steps. No feature bloat, no dashboard you never open.
          </p>
        </div>

        <BentoGridShowcase
          integrations={
            <BentoCard
              title="Step 1 · Define your offer"
              description="Structured prompts for product, audience, and pricing."
            >
              <MediaPlaceholder />
            </BentoCard>
          }
          mainFeature={
            <BentoCard
              title="Launch checklist"
              description="Track domain, payments, analytics, and legal basics in one list."
            >
              <div className="space-y-2">
                {["Define offer", "Publish page", "Connect payments", "Analytics"].map(
                  (step, i) => (
                    <div
                      key={step}
                      className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                    >
                      <CheckSquare
                        className={`size-4 ${i < 2 ? "text-[#2563eb]" : "text-muted-foreground"}`}
                      />
                      <span className={i < 2 ? "text-foreground" : "text-muted-foreground"}>
                        {step}
                      </span>
                    </div>
                  )
                )}
              </div>
            </BentoCard>
          }
          featureTags={
            <BentoCard title="Built for founders" description="No design decisions upfront.">
              <div className="flex flex-wrap gap-2">
                {["Offer", "Landing", "Launch"].map((tag) => (
                  <span
                    key={tag}
                    className="rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </BentoCard>
          }
          secondaryFeature={
            <BentoCard
              title="Step 2 · Build your page"
              description="Export copy, CTA, and form without a design tool."
            >
              <LayoutTemplate className="mb-2 size-5 text-[#2563eb]" aria-hidden />
              <MediaPlaceholder />
            </BentoCard>
          }
          statistic={
            <BentoCard
              title="Step 3 · Ship with confidence"
              description="Nothing gets missed on day one."
            >
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold tracking-tight text-foreground">3</span>
                <span className="pb-1 text-sm text-muted-foreground">focused steps</span>
              </div>
              <FileText className="mt-4 size-5 text-muted-foreground" aria-hidden />
            </BentoCard>
          }
          journey={
            <BentoCard title="From idea to launch" description="One path, no detours.">
              <Layers className="size-5 text-[#2563eb]" aria-hidden />
            </BentoCard>
          }
        />
      </div>
    </section>
  )
}
