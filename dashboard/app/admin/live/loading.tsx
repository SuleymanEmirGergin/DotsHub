export default function Loading() {
  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-5">
      {/* Title + control buttons */}
      <div className="flex items-center justify-between">
        <div className="space-y-1.5">
          <div className="h-8 w-48 bg-muted animate-pulse rounded-lg" />
          <div className="h-4 w-64 bg-muted animate-pulse rounded" />
        </div>
        <div className="flex gap-2">
          <div className="h-9 w-28 bg-muted animate-pulse rounded-lg" />
          <div className="h-9 w-20 bg-muted animate-pulse rounded-lg" />
        </div>
      </div>

      {/* 4 stat cards (total / active / waiting / completed) */}
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 bg-muted animate-pulse rounded-2xl" />
        ))}
      </div>

      {/* Live sessions table */}
      <div className="border border-border rounded-2xl overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-8 gap-3 p-3 bg-muted/50">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-4 bg-muted animate-pulse rounded" />
          ))}
        </div>
        {/* Rows */}
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="grid grid-cols-8 gap-3 p-3 border-t border-border">
            <div className="h-6 w-20 bg-muted animate-pulse rounded-lg" />
            <div className="h-4 bg-muted animate-pulse rounded" />
            <div className="h-5 w-16 bg-muted animate-pulse rounded-md" />
            <div className="h-4 w-6 bg-muted animate-pulse rounded" />
            <div className="h-4 bg-muted animate-pulse rounded" />
            <div className="h-4 w-10 bg-muted animate-pulse rounded" />
            <div className="col-span-2 h-4 bg-muted animate-pulse rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
