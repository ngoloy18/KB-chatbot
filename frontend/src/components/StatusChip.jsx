const toneClass = {
  green: "bg-emerald-50 text-emerald-700 border-emerald-100",
  teal: "bg-teal-50 text-med-primary border-teal-100",
  blue: "bg-sky-50 text-sky-700 border-sky-100",
  amber: "bg-amber-50 text-amber-700 border-amber-100",
  red: "bg-red-50 text-red-700 border-red-100",
  gray: "bg-slate-50 text-slate-600 border-slate-100",
};

export function StatusChip({ children, tone = "gray" }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${toneClass[tone] || toneClass.gray}`}>
      {children}
    </span>
  );
}
