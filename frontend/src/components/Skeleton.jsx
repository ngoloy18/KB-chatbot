export function SkeletonBlock({ className = "" }) {
  return <span className={`block animate-pulse rounded-lg bg-slate-200/80 ${className}`} aria-hidden="true" />;
}

export function TableSkeletonRows({ rows = 4, columns = 5 }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={`skeleton-row-${rowIndex}`}>
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <td className="border-b border-med-border p-4" key={`skeleton-cell-${rowIndex}-${columnIndex}`}>
              <SkeletonBlock className={columnIndex === 0 ? "h-4 w-4" : "h-4 w-full max-w-[180px]"} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
