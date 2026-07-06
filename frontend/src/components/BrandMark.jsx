import logoUrl from "../assets/kb-chat-logo.png";

export function BrandMark({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <img
        src={logoUrl}
        alt="KB-Chat Bot Dev logo"
        className="h-11 w-11 shrink-0 rounded-[10px] bg-white object-cover"
      />
      {!compact && (
        <div>
          <p className="text-xl font-black leading-none text-med-primary">KB-Chat Bot Dev</p>
          <p className="mt-1 text-xs font-semibold text-med-text">AI Developer Assistant</p>
        </div>
      )}
    </div>
  );
}
