export default function Loading() {
  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-5">
      {/* Title */}
      <div className="h-8 w-52 bg-muted animate-pulse rounded-lg" />
      <div className="h-4 w-72 bg-muted animate-pulse rounded" />

      {/* 2-column layout: sidebar + content */}
      <div className="grid grid-cols-[280px_1fr] gap-4">
        {/* Report file list */}
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>

        {/* Report content */}
        <div className="flex flex-col gap-4">
          {/* 2-col cards */}
          <div className="grid grid-cols-2 gap-3">
            <div className="h-48 bg-muted animate-pulse rounded-2xl" />
            <div className="h-48 bg-muted animate-pulse rounded-2xl" />
          </div>
          {/* Synonym table card */}
          <div className="h-56 bg-muted animate-pulse rounded-2xl" />
          {/* Question effectiveness card */}
          <div className="h-40 bg-muted animate-pulse rounded-2xl" />
          {/* 2-col bottom cards */}
          <div className="grid grid-cols-2 gap-3">
            <div className="h-40 bg-muted animate-pulse rounded-2xl" />
            <div className="h-40 bg-muted animate-pulse rounded-2xl" />
          </div>
        </div>
      </div>
    </div>
  );
}
