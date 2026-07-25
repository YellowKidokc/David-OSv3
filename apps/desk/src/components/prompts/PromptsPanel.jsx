import { useState, useMemo } from 'react';
import {
  Sparkles,
  Zap,
  Search,
  Copy,
  Check,
  MessageSquare,
  BrainCircuit,
  Target,
  FileText,
  Code,
  Lightbulb,
  Flame,
  Command,
  Plus,
  X,
} from 'lucide-react';

/*
  PromptsPanel — a full prompt library.
  Categories, search, one-click copy to composer.
  Categories match David's command vocabulary and daily workflow.
  Custom prompts persist to localStorage (topOfMind.customPrompts.v1).
*/

const CUSTOM_PROMPTS_KEY = 'topOfMind.customPrompts.v1';

const CATEGORIES = [
  { id: 'analysis', label: 'Analysis', icon: BrainCircuit },
  { id: 'research', label: 'Research', icon: Search },
  { id: 'writing', label: 'Writing', icon: FileText },
  { id: 'code', label: 'Code', icon: Code },
  { id: 'strategy', label: 'Strategy', icon: Target },
  { id: 'creative', label: 'Creative', icon: Lightbulb },
  { id: 'debate', label: 'Debate', icon: Flame },
  { id: 'ops', label: 'Hub Ops', icon: Command },
  { id: 'custom', label: 'Custom', icon: Plus },
];

const PROMPTS = [
  // Analysis
  { id: 'a1', category: 'analysis', label: 'Deep dive', text: 'Take a deep dive into this. Explore all angles, identify hidden assumptions, and build a structured analysis with evidence for each claim.', tags: ['probe', 'research'] },
  { id: 'a2', category: 'analysis', label: 'Map the landscape', text: 'Map the full intellectual landscape around this topic. What are the dominant schools of thought, who are the key figures, and where are the open questions?', tags: ['research', 'overview'] },
  { id: 'a3', category: 'analysis', label: 'Find the crux', text: 'What is the single most important question here — the one that, if answered, would resolve the most uncertainty? State it clearly and explain why.', tags: ['focus', 'clarity'] },
  { id: 'a4', category: 'analysis', label: 'Assumption audit', text: "List every implicit assumption in this argument. For each one: is it justified? What happens if it's wrong?", tags: ['critical', 'probe'] },
  { id: 'a5', category: 'analysis', label: 'Evidence check', text: 'What empirical evidence exists for and against this claim? Separate strong evidence from weak, and flag anything that needs verification.', tags: ['empirical', 'verify'] },

  // Writing
  { id: 'w1', category: 'writing', label: 'Simplify', text: 'Explain this in the simplest possible terms. Use analogies. Assume I am a beginner but don\'t talk down to me.', tags: ['clarity', 'beginner'] },
  { id: 'w2', category: 'writing', label: 'Elevator pitch', text: 'Distill this into a 30-second elevator pitch. One sentence for the problem, one for the solution, one for why it matters.', tags: ['distill', 'pitch'] },
  { id: 'w3', category: 'writing', label: 'Grant paragraph', text: 'Write this as a grant proposal paragraph. Lead with impact, cite evidence, and end with a clear ask. Tone: confident, grounded, ambitious.', tags: ['templeton', 'grant'] },
  { id: 'w4', category: 'writing', label: 'Academic tone', text: 'Rewrite this in formal academic prose. Use precise terminology, passive voice where appropriate, and maintain scholarly distance.', tags: ['academic', 'formal'] },
  { id: 'w5', category: 'writing', label: 'Story mode', text: 'Turn this into a narrative. Use concrete characters, scenes, and tension. Make the abstract feel lived.', tags: ['narrative', 'story'] },

  // Code
  { id: 'c1', category: 'code', label: 'Code review', text: 'Review this code as a senior engineer. Flag bugs, performance issues, and style problems. Suggest specific improvements.', tags: ['review', 'engineering'] },
  { id: 'c2', category: 'code', label: 'Add types', text: 'Add TypeScript types to this code. Be strict — no `any` unless absolutely necessary. Export interfaces for all public APIs.', tags: ['typescript', 'types'] },
  { id: 'c3', category: 'code', label: 'Write tests', text: 'Write a comprehensive test suite for this code. Cover happy paths, edge cases, and error conditions. Use descriptive test names.', tags: ['testing', 'quality'] },
  { id: 'c4', category: 'code', label: 'Debug mode', text: 'Something is wrong with this code. Walk through it line by line, state your assumptions at each step, and identify the bug.', tags: ['debug', 'troubleshoot'] },
  { id: 'c5', category: 'code', label: 'Refactor', text: 'Refactor this for clarity and maintainability. Reduce nesting, extract functions, and eliminate duplication. Preserve all behavior.', tags: ['clean', 'refactor'] },

  // Strategy
  { id: 's1', category: 'strategy', label: 'Decision matrix', text: 'Frame this as a decision matrix. List the options, criteria, and trade-offs. Recommend the best path with your reasoning.', tags: ['decision', 'planning'] },
  { id: 's2', category: 'strategy', label: 'Risk scan', text: 'Scan this plan for risks — technical, financial, reputational, and timeline. Rate each risk and suggest mitigations.', tags: ['risk', 'planning'] },
  { id: 's3', category: 'strategy', label: 'Next 3 steps', text: 'What are the exact next 3 steps? Be specific about who does what, by when, and what "done" looks like for each.', tags: ['action', 'tactical'] },
  { id: 's4', category: 'strategy', label: 'Templeton angle', text: 'How would the John Templeton Foundation evaluate this? Frame it in terms of: big questions, interdisciplinary bridge-building, and measurable impact.', tags: ['templeton', 'grant'] },
  { id: 's5', category: 'strategy', label: 'Opposition prep', text: 'An expert skeptic is about to challenge this. What are their strongest arguments? Prepare rebuttals and identify where we should concede.', tags: ['debate', 'defense'] },

  // Creative
  { id: 'cr1', category: 'creative', label: 'Metaphor engine', text: 'Generate 5 original metaphors for this concept. Each should illuminate a different aspect. Avoid cliches.', tags: ['metaphor', 'fresh'] },
  { id: 'cr2', category: 'creative', label: 'Name it', text: 'Generate 10 names for this project/concept. Mix Greek roots, physics terms, and theological language. Check for uniqueness.', tags: ['branding', 'naming'] },
  { id: 'cr3', category: 'creative', label: 'Visual description', text: 'Describe what this would look like as a visual — a diagram, an infographic, or a scene. Be specific about layout, colors, and flow.', tags: ['visual', 'design'] },
  { id: 'cr4', category: 'creative', label: 'Analogy from another field', text: 'Find an analogy for this concept from a completely different field — biology, music, cooking, warfare. Explain the mapping in detail.', tags: ['cross-domain', 'analogy'] },

  // Debate
  { id: 'd1', category: 'debate', label: 'Steel-man', text: 'Steel-man the opposing view. Present it in its strongest form — stronger than most advocates would. Then identify its weakest point.', tags: ['fair', 'strongest'] },
  { id: 'd2', category: 'debate', label: "Devil's advocate", text: "Play devil's advocate against this position. Raise the 3 strongest objections. Do not hold back.", tags: ['critical', 'objections'] },
  { id: 'd3', category: 'debate', label: 'Synthesize', text: 'Both sides have merit. Synthesize a position that captures the truth in each, resolves the tension, and moves the conversation forward.', tags: ['synthesis', 'resolution'] },
  { id: 'd4', category: 'debate', label: 'What would change your mind', text: 'For this belief/position: what specific evidence or argument would change your mind? If nothing would, say that and explain why.', tags: ['epistemic', 'honesty'] },

  // Research (Theophysics / derivation workflow)
  { id: 'r1', category: 'research', label: 'Derive it', text: 'Take this claim from intuition to derivation. State the axioms, show each step formally, and flag any step that relies on assumption rather than proof.', tags: ['derivation', 'formal'] },
  { id: 'r2', category: 'research', label: 'Pressure test (R5)', text: 'Run this through a hostile rigor pass. Try to break it. Find the weakest axiom, the leakiest inference, and the claim most likely to embarrass me in front of experts. Do not be polite.', tags: ['r5', 'adversarial'] },
  { id: 'r3', category: 'research', label: 'Probe the axiom', text: 'PROBE this axiom before release: is it load-bearing? Is it falsifiable? What observation would kill it? What cheaper axiom would do the same work?', tags: ['probe', 'axiom'] },
  { id: 'r4', category: 'research', label: 'Lossless compression', text: 'Compress this session into a lossless artifact an AI can reconstruct full context from in a new conversation. Preserve decisions, open threads, naming, and tone. Optimize for fidelity, not readability.', tags: ['continuity', 'compression'] },
  { id: 'r5', category: 'research', label: 'Isomorphism check', text: 'Map this structure onto its isomorphisms across domains (physics, theology, information). For each mapping: what survives the mapping exactly, and where does the analogy break?', tags: ['isomorphism', 'structure'] },

  // Hub Ops
  { id: 'o1', category: 'ops', label: 'Filesystem intake', text: '/api filesystem intake ', tags: ['fis', 'slash'] },
  { id: 'o2', category: 'ops', label: 'Near-dup scan', text: '/api filesystem neardup', tags: ['fis', 'slash'] },
  { id: 'o3', category: 'ops', label: 'Classify file', text: '/api nlp classify ', tags: ['nlp', 'slash'] },
  { id: 'o4', category: 'ops', label: 'Send to channel', text: '/api comm send codex "', tags: ['mattermost', 'slash'] },
  { id: 'o5', category: 'ops', label: 'Broadcast', text: '/api comm broadcast ', tags: ['mattermost', 'slash'] },
];

function loadCustomPrompts() {
  try {
    const saved = JSON.parse(localStorage.getItem(CUSTOM_PROMPTS_KEY) || '[]');
    return Array.isArray(saved) ? saved : [];
  } catch { return []; }
}

export function PromptsPanel({ onCopyToComposer }) {
  const [activeCategory, setActiveCategory] = useState('analysis');
  const [search, setSearch] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [customPrompts, setCustomPrompts] = useState(loadCustomPrompts);
  const [formOpen, setFormOpen] = useState(false);
  const [draft, setDraft] = useState({ label: '', text: '', tags: '' });

  const allPrompts = useMemo(() => [...PROMPTS, ...customPrompts], [customPrompts]);

  const filtered = useMemo(() => {
    let list = allPrompts.filter((p) => p.category === activeCategory);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = allPrompts.filter(
        (p) =>
          p.label.toLowerCase().includes(q) ||
          p.text.toLowerCase().includes(q) ||
          p.tags.some((t) => t.includes(q))
      );
    }
    return list;
  }, [allPrompts, activeCategory, search]);

  const handleCopy = (prompt) => {
    onCopyToComposer?.(prompt.text);
    setCopiedId(prompt.id);
    setTimeout(() => setCopiedId(null), 1200);
  };

  const persistCustom = (next) => {
    setCustomPrompts(next);
    localStorage.setItem(CUSTOM_PROMPTS_KEY, JSON.stringify(next));
  };

  const saveCustomPrompt = () => {
    const label = draft.label.trim();
    const text = draft.text.trim();
    if (!label || !text) return;
    const prompt = {
      id: `custom-${Date.now()}`,
      category: 'custom',
      label,
      text,
      tags: draft.tags.split(',').map((t) => t.trim()).filter(Boolean),
      custom: true,
    };
    persistCustom([...customPrompts, prompt]);
    setDraft({ label: '', text: '', tags: '' });
    setFormOpen(false);
    setActiveCategory('custom');
  };

  const deleteCustomPrompt = (id) => persistCustom(customPrompts.filter((p) => p.id !== id));

  return (
    <section className="prompts-panel">
      <div className="prompts-header">
        <h3>
          <Sparkles size={15} /> Prompt Library
        </h3>
        <p>{allPrompts.length} prompts across {CATEGORIES.length} categories</p>
      </div>

      <div className="prompts-search">
        <Search size={14} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search prompts by name, text, or tag..."
        />
        {search && (
          <button className="prompts-clear" onClick={() => setSearch('')}>
            Clear
          </button>
        )}
        <button className="prompts-new" onClick={() => setFormOpen(!formOpen)}>
          <Plus size={13} /> New
        </button>
      </div>

      {formOpen && (
        <div className="prompt-form">
          <input
            value={draft.label}
            onChange={(e) => setDraft({ ...draft, label: e.target.value })}
            placeholder="Prompt name (e.g. Morning triage)"
          />
          <textarea
            value={draft.text}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            placeholder="Prompt text — this is what lands in the composer."
            rows={3}
          />
          <div className="prompt-form-row">
            <input
              value={draft.tags}
              onChange={(e) => setDraft({ ...draft, tags: e.target.value })}
              placeholder="tags, comma separated"
            />
            <button className="tm-primary" onClick={saveCustomPrompt} disabled={!draft.label.trim() || !draft.text.trim()}>
              Save prompt
            </button>
            <button onClick={() => setFormOpen(false)}><X size={12} /> Cancel</button>
          </div>
        </div>
      )}

      <div className="prompts-categories">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const count = allPrompts.filter((p) => p.category === cat.id).length;
          return (
            <button
              key={cat.id}
              className={activeCategory === cat.id ? 'active' : ''}
              onClick={() => { setActiveCategory(cat.id); setSearch(''); }}
            >
              <Icon size={14} />
              {cat.label}
              <span className="cat-count">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="prompts-list">
        {filtered.map((p) => (
          <div key={p.id} className="prompt-card">
            <div className="prompt-card-head">
              <Zap size={12} />
              <b>{p.label}</b>
              <div className="prompt-tags">
                {p.tags.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
            </div>
            <p className="prompt-text">{p.text}</p>
            <div className="prompt-card-actions">
              <button
                onClick={() => handleCopy(p)}
                className={copiedId === p.id ? 'copied' : ''}
              >
                {copiedId === p.id ? (
                  <>
                    <Check size={12} /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={12} /> Use
                  </>
                )}
              </button>
              <button
                onClick={() => navigator.clipboard?.writeText?.(p.text)}
                title="Copy to clipboard"
              >
                <MessageSquare size={12} /> Copy
              </button>
              {p.custom && (
                <button onClick={() => deleteCustomPrompt(p.id)} title="Delete custom prompt">
                  <X size={12} /> Delete
                </button>
              )}
            </div>
          </div>
        ))}
        {!filtered.length && (
          <div className="prompts-empty">
            <Search size={32} strokeWidth={1} />
            <p>{activeCategory === 'custom' && !search ? 'No custom prompts yet — hit + New above.' : <>No prompts match &quot;{search}&quot;</>}</p>
          </div>
        )}
      </div>
    </section>
  );
}
