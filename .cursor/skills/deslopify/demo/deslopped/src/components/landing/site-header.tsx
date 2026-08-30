import { AnimatedButton } from "@/components/ui/animated-button"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Home", href: "#", active: true },
  { label: "About", href: "#" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "#" },
]

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
        <a href="#" className="text-sm font-semibold tracking-tight">
          GenericaAI
        </a>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {navItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                item.active && "bg-muted text-foreground"
              )}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <AnimatedButton className="h-8 bg-[#2563eb] px-3 text-xs hover:bg-[#1d4ed8]">
          Get started
        </AnimatedButton>
      </div>
    </header>
  )
}
