import { X } from "lucide-react";

export function Modal({ title, subtitle, children, footer, onClose }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-med-text/25 p-6 backdrop-blur-md">
      <section className="max-h-[calc(100vh-48px)] w-full max-w-3xl overflow-auto rounded-xl border border-med-border bg-white/90 shadow-glass backdrop-blur-xl">
        <header className="flex items-start justify-between gap-4 border-b border-med-border px-6 py-5">
          <div>
            <h2 className="text-xl font-black text-med-text">{title}</h2>
            {subtitle && <p className="mt-1 text-sm text-med-muted">{subtitle}</p>}
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </header>
        <div className="px-6 py-5">{children}</div>
        {footer && <footer className="flex flex-wrap items-center justify-end gap-3 px-6 pb-6">{footer}</footer>}
      </section>
    </div>
  );
}
