import { X, Plus, Link } from "lucide-react";

export default function ManualForm({ manualData, onFieldChange, onSkillAdd, onSkillRemove }) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const skill = manualData.skillsInput.trim().replace(/,+$/, "");
      if (skill && !manualData.skills.includes(skill)) {
        onSkillAdd(skill);
      }
    }
  };

  const handleLinkAdd = () => {
    const url = manualData.linkInput.trim();
    if (url && !manualData.portfolioLinks.includes(url)) {
      onFieldChange("portfolioLinks", [...manualData.portfolioLinks, url]);
      onFieldChange("linkInput", "");
    }
  };

  const handleLinkKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleLinkAdd();
    }
  };

  const handleLinkRemove = (url) => {
    onFieldChange("portfolioLinks", manualData.portfolioLinks.filter((l) => l !== url));
  };

  return (
    <>
      <div className="space-y-4">
        <div>
          <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
            Full Name
          </label>
          <input
            type="text"
            value={manualData.name}
            onChange={(e) => onFieldChange("name", e.target.value)}
            placeholder="Jane Doe"
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
          />
        </div>
        <div>
          <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
            Email
          </label>
          <input
            type="email"
            value={manualData.email}
            onChange={(e) => onFieldChange("email", e.target.value)}
            placeholder="jane@example.com"
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
          />
        </div>
        <div>
          <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
            Skills{" "}
            <span className="text-white/25 normal-case font-normal">
              (press Enter to add)
            </span>
          </label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {manualData.skills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-accent/10 border border-accent/20 rounded-full text-accent text-xs"
              >
                {skill}
                <button
                  onClick={() => onSkillRemove(skill)}
                  className="hover:text-white"
                  aria-label={`Remove skill ${skill}`}
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            value={manualData.skillsInput}
            onChange={(e) => onFieldChange("skillsInput", e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="React, TypeScript, Leadership..."
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
          />
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
            Work Experience
          </label>
          <textarea
            value={manualData.experience}
            onChange={(e) => onFieldChange("experience", e.target.value)}
            placeholder={"Senior Engineer at TechCorp (2021-Present)\n- Led team of 5, shipped 3 major features\n- ..."}
            rows={5}
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
          />
        </div>
        <div>
          <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
            Education
          </label>
          <textarea
            value={manualData.education}
            onChange={(e) => onFieldChange("education", e.target.value)}
            placeholder={"B.S. Computer Science, Stanford (2014-2018)"}
            rows={3}
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all resize-none"
          />
        </div>
        <div>
          <label className="block text-white/50 text-xs font-medium uppercase tracking-wider mb-1.5">
            Portfolio Links{" "}
            <span className="text-white/25 normal-case font-normal">
              (press Enter to add)
            </span>
          </label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {manualData.portfolioLinks.map((url) => (
              <span
                key={url}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-white/[0.05] border border-white/[0.1] rounded-full text-white/60 text-xs max-w-[200px] truncate"
              >
                <Link size={10} className="shrink-0" />
                {url.replace(/^https?:\/\//, "").slice(0, 30)}
                <button
                  onClick={() => handleLinkRemove(url)}
                  className="hover:text-white shrink-0"
                  aria-label={`Remove link ${url}`}
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="url"
              value={manualData.linkInput}
              onChange={(e) => onFieldChange("linkInput", e.target.value)}
              onKeyDown={handleLinkKeyDown}
              placeholder="https://github.com/username"
              className="flex-1 bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
            <button
              type="button"
              onClick={handleLinkAdd}
              disabled={!manualData.linkInput.trim()}
              className="px-3 py-3 bg-white/[0.05] border border-white/[0.1] rounded-xl text-white/50 hover:text-white hover:bg-white/[0.08] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <Plus size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
