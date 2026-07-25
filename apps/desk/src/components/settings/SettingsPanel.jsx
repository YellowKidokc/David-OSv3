import { useEffect, useMemo, useState } from 'react';
import { NUMBERING, topOfMindApi } from '../../lib/api/topOfMindApi';
import {
  Plug,
  Sparkles,
  MessageSquare,
  Bot,
  Code,
  Wrench,
  Keyboard,
  Clipboard,
  Check,
  Copy,
  AlertTriangle,
} from 'lucide-react';

/*
  SettingsPanel — the filled-out settings structure for Top of Mind Desk.
  Sections: Connection, Appearance, System Prompt, Providers & Keys,
  Numbering Defaults, Workspace, Keyboard, Local Data.
  Everything persists to localStorage under the topOfMind.* namespace,
  matching the keys the rest of the app already reads.
*/

const THEME_KEY = 'topOfMind.theme';
const FONT_KEY = 'topOfMind.fontSize';
const SYSTEM_PROMPT_KEY = 'topOfMind.systemPrompt';
const POLL_KEY = 'topOfMind.pollMs';
const WALL_KEY = 'topOfMind.defaultWall';
const FOLDER_KEY = 'topOfMind.defaultFolder';

const DEFAULT_SYSTEM_PROMPT = 'You are David OS: concise, structured, and action oriented.';

const NAV = [
  { id: 'connection', label: 'Connection', icon: Plug },
  { id: 'appearance', label: 'Appearance', icon: Sparkles },
  { id: 'prompt', label: 'System Prompt', icon: MessageSquare },
  { id: 'providers', label: 'Providers & Keys', icon: Bot },
  { id: 'numbering', label: 'Numbering', icon: Code },
  { id: 'workspace', label: 'Workspace', icon: Wrench },
  { id: 'keyboard', label: 'Keyboard', icon: Keyboard },
  { id: 'data', label: 'Local Data', icon: Clipboard },
];

const PROVIDERS = [
  { id: 'openai', name: 'OpenAI', env: 'OPENAI_API_KEY', use: 'GPT models, embeddings, agents', docs: 'https://platform.openai.com/docs' },
  { id: 'anthropic', name: 'Anthropic', env: 'ANTHROPIC_API_KEY', use: 'Claude models (Opus, Sonnet)', docs: 'https://docs.anthropic.com' },
  { id: 'gemini', name: 'Google Gemini', env: 'GEMINI_API_KEY', use: 'Deep research, NotebookLM bridge', docs: 'https://ai.google.dev/docs' },
  { id: 'deepseek', name: 'DeepSeek', env: 'DEEPSEEK_API_KEY', use: 'Station 17 pipeline', docs: 'https://platform.deepseek.com' },
  { id: 'kimi', name: 'Kimi (Moonshot)', env: 'MOONSHOT_API_KEY', use: 'Kimi CLI agent lane', docs: 'https://platform.moonshot.ai' },
  { id: 'ollama', name: 'Ollama', env: 'http://192.168.2.50:11434', use: 'Local LLM inference on the NAS', docs: 'https://ollama.com' },
  { id: 'mattermost', name: 'Mattermost', env: 'MATTERMOST_TOKEN', use: 'Agent channel send/broadcast', docs: '' },
  { id: 'cloudflare', name: 'Cloudflare', env: 'CLOUDFLARE_API_TOKEN', use: 'Pages deploys, DNS, R2', docs: 'https://dash.cloudflare.com' },
  { id: 'r2', name: 'Cloudflare R2', env: 'R2_ACCESS_KEY_ID / R2_SECRET', use: 'Media bucket storage', docs: 'https://developers.cloudflare.com/r2/' },
  { id: 'synology', name: 'Synology NAS', env: 'http://192.168.2.50:5000', use: 'NAS storage, Docker, Chat', docs: '' },
  { id: 'postgres', name: 'PostgreSQL', env: '192.168.2.50:5432', use: 'Axiom database, canonical nodes', docs: '' },
  { id: 'ahk', name: 'AHK Bridge', env: 'AHK_BRIDGE_URL', use: 'Desktop paste/send/overlay control', docs: '' },
];

const SHORTCUTS = [
  ['Ctrl / Cmd + K', 'Open the command palette'],
  ['Esc', 'Close palette, menus, and modals'],
  ['↑ / ↓', 'Move through palette results'],
  ['Enter', 'Run highlighted palette action'],
  ['Enter (composer)', 'Send message to active source'],
  ['Shift + Enter (composer)', 'New line without sending'],
  ['/api …', 'Slash commands route straight to hub APIs'],
];

function applyTheme(theme) {
  document.body.classList.toggle('theme-void', theme !== 'slate');
  document.body.classList.toggle('theme-slate', theme === 'slate');
}
function applyFontSize(size) {
  document.documentElement.style.fontSize = size === 'compact' ? '14px' : size === 'large' ? '18px' : '16px';
}

function ConnectionSection({ online, setOnline, setNotice }) {
  const [url, setUrl] = useState(topOfMindApi.baseUrl);
  const [testing, setTesting] = useState(false);
  async function test(target = url) {
    setTesting(true);
    topOfMindApi.setBaseUrl(target);
    try { await topOfMindApi.test(); setOnline(true); setNotice?.(`Hub online at ${topOfMindApi.baseUrl}`); }
    catch (e) { setOnline(false); setNotice?.(`Hub offline: ${e.message}`); }
    finally { setTesting(false); }
  }
  return (
    <div className="settings-card">
      <h3><Plug size={14} /> Hub connection</h3>
      <p>Base URL for the local FastAPI hub. Saved to localStorage and used by every panel in the desk.</p>
      <div className="settings-grid">
        <label className="settings-field full">API base URL
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://127.0.0.1:10000" />
        </label>
      </div>
      <div className="settings-actions">
        <button className="tm-primary" disabled={testing} onClick={() => test()}>{testing ? 'Testing…' : 'Save + Test'}</button>
        <button onClick={() => { setUrl('http://127.0.0.1:10000'); test('http://127.0.0.1:10000'); }}>Reset to default</button>
        <button onClick={async () => { try { const d = await topOfMindApi.hubHealth(); setNotice?.(`Hub health: ${JSON.stringify(d).slice(0, 120)}`); } catch (e) { setNotice?.(`Health check failed: ${e.message}`); } }}>Hub health</button>
        <span className={`status ${online ? 'ok' : 'bad'}`}>{online ? '● online' : '○ offline'}</span>
      </div>
    </div>
  );
}

function AppearanceSection({ setNotice }) {
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || 'void');
  const [font, setFont] = useState(() => localStorage.getItem(FONT_KEY) || 'standard');
  const pick = (t) => { setTheme(t); localStorage.setItem(THEME_KEY, t); applyTheme(t); setNotice?.(`Theme: ${t === 'void' ? 'Void Black' : 'Slate Blue'}`); };
  const pickFont = (f) => { setFont(f); localStorage.setItem(FONT_KEY, f); applyFontSize(f); };
  return (
    <div className="settings-card">
      <h3><Sparkles size={14} /> Appearance</h3>
      <p>Void Black is the default blacked-out look with gold accents. Slate Blue restores the original palette.</p>
      <div className="theme-swatches">
        <button className={`theme-swatch ${theme === 'void' ? 'active' : ''}`} onClick={() => pick('void')}>
          <div className="swatch-preview swatch-void"><i /><em /></div>
          <b>Void Black</b>
          <small>Blacked out · gold accents</small>
        </button>
        <button className={`theme-swatch ${theme === 'slate' ? 'active' : ''}`} onClick={() => pick('slate')}>
          <div className="swatch-preview swatch-slate"><i /><em /></div>
          <b>Slate Blue</b>
          <small>Original · cyan accents</small>
        </button>
      </div>
      <div className="settings-actions">
        <label className="settings-field">Font size
          <select value={font} onChange={(e) => pickFont(e.target.value)}>
            <option value="compact">Compact</option>
            <option value="standard">Standard</option>
            <option value="large">Large</option>
          </select>
        </label>
      </div>
    </div>
  );
}

function SystemPromptSection({ setNotice }) {
  const [text, setText] = useState(() => localStorage.getItem(SYSTEM_PROMPT_KEY) || DEFAULT_SYSTEM_PROMPT);
  const [saved, setSaved] = useState(false);
  const save = () => { localStorage.setItem(SYSTEM_PROMPT_KEY, text); setSaved(true); setNotice?.('System prompt saved.'); setTimeout(() => setSaved(false), 1200); };
  return (
    <div className="settings-card">
      <h3><MessageSquare size={14} /> System prompt</h3>
      <p>The outside instruction layer. Same prompt the sidebar ☉ button edits — it ships with chat and prompt launches.</p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} />
      <div className="settings-actions">
        <button className="tm-primary" onClick={save}>{saved ? <><Check size={12} /> Saved</> : 'Save prompt'}</button>
        <button onClick={() => setText(DEFAULT_SYSTEM_PROMPT)}>Reset to default</button>
        <button onClick={() => { navigator.clipboard?.writeText?.(text); setNotice?.('System prompt copied.'); }}><Copy size={12} /> Copy</button>
      </div>
    </div>
  );
}

function ProvidersSection() {
  return (
    <div className="settings-card">
      <h3><Bot size={14} /> Providers & keys</h3>
      <p>Keys live on the hub server as environment variables — never in this frontend. This table is the wiring map: which env var each lane reads and what it powers.</p>
      <table className="settings-table">
        <thead><tr><th>Provider</th><th>Env var / endpoint</th><th>Powers</th><th></th></tr></thead>
        <tbody>
          {PROVIDERS.map((p) => (
            <tr key={p.id}>
              <td><b>{p.name}</b></td>
              <td><code>{p.env}</code></td>
              <td>{p.use}</td>
              <td>{p.docs ? <button onClick={() => window.open(p.docs, '_blank', 'noopener')}>Docs</button> : <span className="muted">local</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NumberingSection() {
  const groups = [
    ['Sources', NUMBERING.sources],
    ['Message types', NUMBERING.types],
    ['Priorities', NUMBERING.priorities],
    ['Walls', NUMBERING.walls],
    ['Folders', NUMBERING.folders],
  ];
  return (
    <div className="settings-card">
      <h3><Code size={14} /> Numbering defaults</h3>
      <p>Canonical numeric codes attached to every message post. Kept in sync with the hub numbering scheme.</p>
      {groups.map(([label, map]) => (
        <table className="settings-table" key={label}>
          <thead><tr><th colSpan="2">{label}</th></tr></thead>
          <tbody>
            {Object.entries(map).map(([k, v]) => <tr key={k}><td>{k}</td><td><code>{v}</code></td></tr>)}
          </tbody>
        </table>
      ))}
    </div>
  );
}

function WorkspaceSection({ setNotice }) {
  const [wall, setWall] = useState(() => localStorage.getItem(WALL_KEY) || 'main');
  const [folder, setFolder] = useState(() => localStorage.getItem(FOLDER_KEY) || 'inbox');
  const [poll, setPoll] = useState(() => localStorage.getItem(POLL_KEY) || '4000');
  const save = () => {
    localStorage.setItem(WALL_KEY, wall);
    localStorage.setItem(FOLDER_KEY, folder);
    localStorage.setItem(POLL_KEY, String(Math.max(1000, Number(poll) || 4000)));
    setNotice?.('Workspace defaults saved. Refresh to apply the new poll interval.');
  };
  return (
    <div className="settings-card">
      <h3><Wrench size={14} /> Workspace defaults</h3>
      <p>Where new messages land and how often the desk polls the hub for fresh messages.</p>
      <div className="settings-grid">
        <label className="settings-field">Default wall
          <select value={wall} onChange={(e) => setWall(e.target.value)}>
            <option value="main">Main wall</option>
            <option value="code">Code wall</option>
          </select>
        </label>
        <label className="settings-field">Default folder
          <select value={folder} onChange={(e) => setFolder(e.target.value)}>
            <option value="inbox">Inbox</option>
            <option value="active">Active</option>
          </select>
        </label>
        <label className="settings-field">Message poll interval (ms)
          <input type="number" min="1000" step="500" value={poll} onChange={(e) => setPoll(e.target.value)} />
        </label>
      </div>
      <div className="settings-actions">
        <button className="tm-primary" onClick={save}>Save defaults</button>
      </div>
    </div>
  );
}

function KeyboardSection() {
  return (
    <div className="settings-card">
      <h3><Keyboard size={14} /> Keyboard</h3>
      <p>Current shortcut map. The command palette (Ctrl/Cmd+K) covers navigation, agents, folders, and /api commands.</p>
      {SHORTCUTS.map(([keys, desc]) => (
        <div className="kbd-row" key={keys}><span>{desc}</span><kbd>{keys}</kbd></div>
      ))}
    </div>
  );
}

function DataSection({ setNotice }) {
  const [keys, setKeys] = useState([]);
  const refresh = () => setKeys(Object.keys(localStorage).filter((k) => k.startsWith('topOfMind')).sort());
  useEffect(refresh, []);
  const exportSnapshot = async () => {
    const snapshot = Object.fromEntries(keys.map((k) => [k, localStorage.getItem(k)]));
    await navigator.clipboard?.writeText?.(JSON.stringify(snapshot, null, 2));
    setNotice?.(`Copied ${keys.length} local settings as JSON.`);
  };
  const clearKey = (k) => { localStorage.removeItem(k); refresh(); setNotice?.(`Removed ${k}`); };
  const clearAll = () => {
    if (!window.confirm('Clear ALL Top of Mind local settings? Theme, prompts, custom agents, and API overrides will reset.')) return;
    keys.forEach((k) => localStorage.removeItem(k));
    refresh();
    setNotice?.('Local settings cleared. Reload to see defaults.');
  };
  const rows = useMemo(() => keys.map((k) => {
    const v = localStorage.getItem(k) || '';
    return [k, v.length > 60 ? `${v.slice(0, 60)}… (${v.length} chars)` : v];
  }), [keys]);
  return (
    <div className="settings-card">
      <h3><Clipboard size={14} /> Local data</h3>
      <p>Everything the desk stores in this browser. Export a snapshot before wiping, or clear individual keys.</p>
      <div className="settings-actions" style={{ marginTop: 0, marginBottom: 10 }}>
        <button className="tm-primary" onClick={exportSnapshot}><Copy size={12} /> Export snapshot</button>
        <button onClick={refresh}>Refresh list</button>
        <button className="danger" onClick={clearAll}><AlertTriangle size={12} /> Clear all local settings</button>
      </div>
      {rows.length ? rows.map(([k, v]) => (
        <div className="ls-key-row" key={k}>
          <code>{k}</code>
          <span className="muted" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v}</span>
          <button onClick={() => clearKey(k)}>Clear</button>
        </div>
      )) : <p className="muted">No topOfMind.* keys stored yet.</p>}
    </div>
  );
}

export function SettingsPanel({ online, setOnline, setNotice }) {
  const [section, setSection] = useState('connection');
  const sections = {
    connection: <ConnectionSection online={online} setOnline={setOnline} setNotice={setNotice} />,
    appearance: <AppearanceSection setNotice={setNotice} />,
    prompt: <SystemPromptSection setNotice={setNotice} />,
    providers: <ProvidersSection />,
    numbering: <NumberingSection />,
    workspace: <WorkspaceSection setNotice={setNotice} />,
    keyboard: <KeyboardSection />,
    data: <DataSection setNotice={setNotice} />,
  };
  return (
    <section className="settings-page">
      <div className="settings-page-head">
        <h1>Settings</h1>
        <p>Connection, appearance, prompts, providers, numbering, workspace defaults, keyboard, and local data.</p>
      </div>
      <div className="settings-shell">
        <nav className="settings-nav">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={section === item.id ? 'active' : ''} onClick={() => setSection(item.id)}>
                <Icon size={14} /> {item.label}
              </button>
            );
          })}
        </nav>
        <div className="settings-content">{sections[section]}</div>
      </div>
    </section>
  );
}
