export function SocialProofSection() {
  return (
    <section className="border-b border-border py-12" aria-label="Customer logos">
      <div className="mx-auto max-w-5xl px-4 text-center sm:px-6">
        <p className="mb-4 text-sm text-muted-foreground">Used by early-stage founders</p>
        <div className="mx-auto flex min-h-16 max-w-xl items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 text-xs text-muted-foreground">
          {/* TODO: real customer logos — name, asset, permission on file */}
          Logo bar reserved for verified customers
        </div>
      </div>
    </section>
  )
}
