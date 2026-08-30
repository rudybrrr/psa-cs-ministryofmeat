"use client"

import { ArrowRight } from "lucide-react"
import { motion, type Variants } from "framer-motion"

import { AnimatedButton } from "@/components/ui/animated-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.12, delayChildren: 0.08 },
  },
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: "easeOut" },
  },
}

export function HeroSection() {
  return (
    <section className="border-b border-border">
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="mx-auto grid max-w-5xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:items-center lg:py-24"
      >
        <div className="space-y-6 text-left">
          <motion.div variants={itemVariants}>
            <Badge variant="secondary">3-day free trial · No credit card</Badge>
          </motion.div>

          <motion.div variants={itemVariants} className="space-y-4">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Turn your idea into a launched business
            </h1>
            <p className="max-w-md text-base leading-relaxed text-muted-foreground">
              GenericaAI guides you from concept to launch with step-by-step
              tasks, templates, and a checklist you can actually follow.
            </p>
          </motion.div>

          <motion.div variants={itemVariants} className="flex flex-wrap gap-3">
            <AnimatedButton className="gap-2 bg-[#2563eb] hover:bg-[#1d4ed8]">
              Start free trial
              <ArrowRight className="size-4" />
            </AnimatedButton>
            <Button variant="outline" size="lg" nativeButton={false} render={<a href="#pricing" />}>
              See pricing
            </Button>
          </motion.div>
        </div>

        <motion.div variants={itemVariants}>
          <Card className="overflow-hidden">
            <CardHeader className="border-b">
              <CardTitle className="text-sm font-medium">Launch checklist</CardTitle>
              <CardDescription>Week 1 · 2 of 4 complete</CardDescription>
              <div
                className="mt-3 h-1 overflow-hidden rounded-full bg-border"
                role="progressbar"
                aria-valuenow={50}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div className="h-full w-1/2 bg-[#2563eb]" />
              </div>
            </CardHeader>
            <CardContent className="space-y-2 pt-4">
              {[
                { label: "Define offer and pricing", done: true },
                { label: "Publish landing page", done: true },
                { label: "Connect payments", done: false },
                { label: "Set up analytics", done: false },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm"
                >
                  <span className={item.done ? "text-foreground" : "text-muted-foreground"}>
                    {item.label}
                  </span>
                  <span
                    className={
                      item.done
                        ? "text-xs font-medium text-[#2563eb]"
                        : "text-xs text-muted-foreground"
                    }
                  >
                    {item.done ? "Done" : "Pending"}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </section>
  )
}
