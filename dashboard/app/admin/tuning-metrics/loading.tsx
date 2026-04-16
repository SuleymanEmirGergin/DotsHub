export default function Loading() {
  return (
    <div className="p-6 space-y-5">
      <div className="max-w-[1400px] mx-auto space-y-5">
        {/* Title */}
        <div className="h-8 w-56 bg-muted animate-pulse rounded-lg" />
        <div className="h-4 w-80 bg-muted animate-pulse rounded" />

        {/* 3-column stat cards */}
        <div className="grid grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>

        {/* Section title */}
        <div className="h-6 w-52 bg-muted animate-pulse rounded-lg" />
        <div className="h-4 w-64 bg-muted animate-pulse rounded" />

        {/* Question effectiveness table */}
        <div className="bg-muted animate-pulse rounded-2xl">
          {/* Header */}
          <div className="grid grid-cols-7 gap-3 p-3 border-b border-border/40">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-4 bg-muted-foreground/20 animate-pulse rounded" />
            ))}
          </div>
          {/* Rows */}
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="grid grid-cols-7 gap-3 p-3 border-t border-border/40">
              <div className="col-span-2 h-4 bg-muted-foreground/20 animate-pulse rounded" />
              <div className="h-4 bg-muted-foreground/20 animate-pulse rounded" />
              <div className="h-4 bg-muted-foreground/20 animate-pulse rounded" />
              <div className="h-4 bg-muted-foreground/20 animate-pulse rounded" />
              <div className="h-4 bg-muted-foreground/20 animate-pulse rounded" />
              <div className="h-4 w-16 bg-muted-foreground/20 animate-pulse rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
