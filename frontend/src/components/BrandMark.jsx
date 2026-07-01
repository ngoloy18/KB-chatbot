export function BrandMark({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-11 w-11 place-items-center rounded-[10px] border-[3px] border-med-deep bg-white/70 text-3xl font-black leading-none text-med-primary">
        +
      </div>
      {!compact && (
        <div>
          <p className="text-xl font-black leading-none text-med-primary">KB-Chat Bot Dev</p>
          <p className="mt-1 text-xs font-semibold text-med-text">AI Developer Assistant</p>
        </div>
      )}
    </div>
  );
}
