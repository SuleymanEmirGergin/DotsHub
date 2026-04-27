import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Table primitives — shadcn-style, with a11y baked in.
 *
 * a11y review #10: sortable column headers need `aria-sort` +
 * `scope="col"`; a11y review #14: sort indicator should be an icon
 * with `aria-hidden`, NOT a Unicode arrow that screen readers read
 * inconsistently. SortableHeader handles both.
 *
 * Pages compose:
 *
 *     <Table>
 *       <TableHeader>
 *         <TableRow>
 *           <SortableHeader sortKey="created_at" current={sort}
 *                           order={order} hrefBuilder={hrefFor} >
 *             Time
 *           </SortableHeader>
 *           <TableHead>Type</TableHead>
 *         </TableRow>
 *       </TableHeader>
 *       <TableBody>
 *         <TableRow>...</TableRow>
 *       </TableBody>
 *     </Table>
 */

const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
  <div className="w-full overflow-hidden rounded-lg border border-border bg-card shadow-sm">
    <table
      ref={ref}
      className={cn("w-full border-collapse text-sm", className)}
      {...props}
    />
  </div>
));
Table.displayName = "Table";

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead
    ref={ref}
    className={cn("bg-accent border-b-2 border-border", className)}
    {...props}
  />
));
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
));
TableBody.displayName = "TableBody";

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn("border-b border-border transition-colors", className)}
    {...props}
  />
));
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, scope = "col", ...props }, ref) => (
  <th
    ref={ref}
    scope={scope}
    className={cn(
      "p-3.5 text-left text-sm font-semibold text-foreground",
      className
    )}
    {...props}
  />
));
TableHead.displayName = "TableHead";

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td ref={ref} className={cn("p-3.5 text-sm", className)} {...props} />
));
TableCell.displayName = "TableCell";

const TableCaption = React.forwardRef<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-muted-foreground", className)}
    {...props}
  />
));
TableCaption.displayName = "TableCaption";

// ─── SortableHeader ──────────────────────────────────────────────
//
// A clickable column header that flips sort order on activation.
// Renders as `<th>` with `aria-sort` set per the current state and a
// nested `<a href>` for keyboard + URL-state preservation.
//
// Use either `hrefBuilder(nextOrder)` for server-driven sort (most
// common in this dashboard, the audited pages already work that way)
// OR pass a plain `href` string if you've pre-computed the URL.

export type SortOrder = "asc" | "desc";

export interface SortableHeaderProps
  extends React.ThHTMLAttributes<HTMLTableCellElement> {
  /** Column identifier matching the URL `?sort=` value. */
  sortKey: string;
  /** Currently active sort key (from URL params). */
  current: string | undefined;
  /** Currently active sort order (from URL params). */
  order: SortOrder | undefined;
  /** Builds the href the link should navigate to when the user
   * activates this header. Receives the desired NEXT order so the
   * page handler can flip ascending<->descending naturally. */
  hrefBuilder: (sortKey: string, nextOrder: SortOrder) => string;
}

const SortAscIcon = () => (
  <svg
    width={14}
    height={14}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    className="size-3.5 shrink-0"
  >
    <path d="m18 15-6-6-6 6" />
  </svg>
);
const SortDescIcon = () => (
  <svg
    width={14}
    height={14}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    className="size-3.5 shrink-0"
  >
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const SortableHeader = React.forwardRef<
  HTMLTableCellElement,
  SortableHeaderProps
>(({ sortKey, current, order, hrefBuilder, className, children, ...props }, ref) => {
  const isActive = current === sortKey;
  const ariaSort: "ascending" | "descending" | "none" = !isActive
    ? "none"
    : order === "asc"
    ? "ascending"
    : "descending";
  const nextOrder: SortOrder = isActive && order === "desc" ? "asc" : "desc";
  const href = hrefBuilder(sortKey, nextOrder);

  return (
    <th
      ref={ref}
      scope="col"
      aria-sort={ariaSort}
      className={cn(
        "p-3.5 text-left text-sm font-semibold",
        className
      )}
      {...props}
    >
      <a
        href={href}
        className="inline-flex items-center gap-1 text-primary-text no-underline hover:underline"
      >
        <span>{children}</span>
        {isActive && (order === "asc" ? <SortAscIcon /> : <SortDescIcon />)}
      </a>
    </th>
  );
});
SortableHeader.displayName = "SortableHeader";

export {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
};
