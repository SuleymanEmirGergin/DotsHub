export default function Loading() {
  return (
    <div className="p-6 space-y-4">
      {/* Title + health pill */}
      <div className="h-8 w-56 bg-muted animate-pulse rounded-lg" />
      <div className="h-4 w-80 bg-muted animate-pulse rounded" />

      {/* Filter chips row */}
      <div className="flex gap-2 flex-wrap">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="h-8 w-20 bg-muted animate-pulse rounded-full" />
        ))}
      </div>

      {/* Deployments table */}
      <div className="h-96 bg-muted animate-pulse rounded-2xl" />
    </div>
  );
}
