import { EtherealShadow } from "@/components/etheral-shadow"
import { FeaturesSection } from "@/components/landing/features-section"
import { HeroSection } from "@/components/landing/hero-section"
import { PricingSection } from "@/components/landing/pricing-section"
import { SiteFooter } from "@/components/landing/site-footer"
import { SiteHeader } from "@/components/landing/site-header"
import { SocialProofSection } from "@/components/landing/social-proof-section"
import { StatsSection } from "@/components/landing/stats-section"

export function App() {
  return (
    <div className="relative min-h-svh">
      <div className="fixed inset-0 z-0">
        <EtherealShadow
          color="rgba(37, 99, 235, 0.28)"
          animation={{ scale: 50, speed: 40 }}
          noise={{ opacity: 25, scale: 1 }}
          className="h-full w-full"
        />
        <div className="absolute inset-0 bg-background/75" />
      </div>

      <div className="relative z-10">
        <SiteHeader />
        <main>
          <HeroSection />
          <StatsSection />
          <FeaturesSection />
          <SocialProofSection />
          <PricingSection />
        </main>
        <SiteFooter />
      </div>
    </div>
  )
}

export default App
