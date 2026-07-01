export function StatCard({ label, value, detail, icon: Icon }) {
  return (
    <article className="rounded-lg border border-med-border bg-white p-5 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-med-muted">{label}</p>
          <strong className="mt-2 block text-3xl font-black text-med-text">{value}</strong>
        </div>
        {Icon && (
          <span className="grid h-12 w-12 place-items-center rounded-full bg-teal-50 text-med-primary">
            <Icon size={22} />
          </span>
        )}
      </div>
      {detail && <p className="mt-3 text-sm text-med-muted">{detail}</p>}
    </article>
  );
}
