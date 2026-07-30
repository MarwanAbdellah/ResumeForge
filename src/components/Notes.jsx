import { StickyNote } from "lucide-react";

export default function Notes({ value, onChange }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
      <div className="flex items-center gap-2 mb-3">
        <StickyNote size={14} className="text-accent" />
        <span className="text-accent text-xs font-medium">
          Notes for the AI
        </span>
      </div>
      <p className="text-white/40 text-xs mb-3">
        Optional — add context, preferences, or instructions (e.g. "emphasize
        leadership experience", "tailor for a startup role").
      </p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Anything the AI should keep in mind when generating your documents..."
        rows={3}
        className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-[border-color,box-shadow] resize-none"
      />
    </div>
  );
}
