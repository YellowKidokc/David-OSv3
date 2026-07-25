import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { NUMBERING, topOfMindApi } from './lib/api/topOfMindApi';
import { ChatView } from './components/chat/ChatView';
import { Composer } from './components/chat/Composer';
import { SourceFilter } from './components/chat/SourceFilter';
import { PromptsPanel } from './components/prompts/PromptsPanel';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { ClipboardWorkspace } from './components/ClipboardWorkspace';
import { ConversationOSPanel } from './components/ConversationOSPanel';
import { ObjectRegistryPage } from './components/ObjectRegistryPage';
import './styles.css';
import './theme-void.css';

const ACTIVE_AGENT_KEY = 'topOfMind.activeAgentId';
const OP_FAMILY_KEY = 'topOfMind.operationFamily';
const API_SHELF_KEY = 'topOfMind.apiShelf.v1';
const CUSTOM_AGENTS_KEY = 'topOfMind.customAgents.v1';
const COMMAND_FAVORITES_KEY = 'topOfMind.commandFavorites.v1';
const COMMAND_RECENTS_KEY = 'topOfMind.commandRecents.v1';

// ---- fallback data ----
const fallbackSources = [
  { id: 'clipboard', name: 'Clipboard', status: 'online', source_code: NUMBERING.sources.clipboard },
  { id: 'ahk', name: 'AutoHotkey', status: 'online', source_code: NUMBERING.sources.ahk },
  { id: 'codex', name: 'Codex', status: 'online', source_code: NUMBERING.sources.codex },
  { id: 'kimi', name: 'Kimi', status: 'online', source_code: NUMBERING.sources.kimi },
  { id: 'claude', name: 'Claude', status: 'online', source_code: NUMBERING.sources.claude },
  { id: 'gemini', name: 'Gemini', status: 'online', source_code: NUMBERING.sources.gemini },
  { id: 'cursor', name: 'Cursor/Versor', status: 'online', source_code: NUMBERING.sources.cursor },
];
const starterFolders = [
  { id: 'local-inbox', name: 'Inbox', folder_code: NUMBERING.folders.inbox, children: [
    { id: 'local-active', name: 'Active', folder_code: NUMBERING.folders.active }
  ]}
];

// ---- helpers ----
const initials = (s) => (s?.name || s?.label || s?.id || s?.source_id || '?').split(/\s|-/).map((p) => p[0]).join('').slice(0, 3).toUpperCase();
const srcName = (s) => s?.name || s?.label || s?.source_id || s?.id || 'source';
const srcId = (s) => s?.id || s?.source_id || s?.name || s?.label;
const arr = (d, key) => Array.isArray(d) ? d : d?.[key] || [];
const globalNavItems = [
  { id: 'chats', icon: '●', label: 'Chats' },
  { id: 'agents', icon: '♙', label: 'Agents' },
  { id: 'prompts', icon: '▣', label: 'Prompts' },
  { id: 'plugins', icon: '▦', label: 'Plugins' },
  { id: 'models', icon: '⚙', label: 'Models' },
  { id: 'clipboard', icon: '⧉', label: 'Clipboard' },
  { id: 'apis', icon: '⌁', label: 'APIs' },
  { id: 'memory', icon: '◇', label: 'KB' },
  { id: 'workflows', icon: '⟲', label: 'Workflows' },
  { id: 'operator', icon: '⌨', label: 'Ops' },
  { id: 'settings', icon: '☷', label: 'Settings' },
];

// ---- API Registry ----
const API_REGISTRY_KEY = 'topOfMind.apiRegistry.v1';

const apiRegistryCategories = {
  file_system: {
    label: 'File System',
    icon: '▣',
    aliases: ['filesystem', 'file', 'fis'],
    apis: [
      { id: 'fis_intake', name: 'Intake Router', endpoint: 'POST /fis/intake', desc: 'Route files to correct locations', status: 'configured', icon: '⇄', params: ['source_folder'] },
      { id: 'fis_neardup', name: 'Near-Dup Scanner', endpoint: 'POST /fis/neardup', desc: 'Find duplicate and similar files', status: 'configured', icon: '≋', params: [] },
      { id: 'fis_crossfolder', name: 'Cross-Folder Scan', endpoint: 'POST /fis/crossfolder', desc: 'Structural fingerprint comparison', status: 'configured', icon: '⌘', params: ['folders'] },
      { id: 'fis_classify', name: 'Classify File', endpoint: 'POST /fis/classify', desc: 'Domain classification for a single file', status: 'configured', icon: '◇', params: ['file_path'] },
      { id: 'file_actions', name: 'File Actions', endpoint: 'POST /operator/file-actions', desc: 'Write, append, delete with review gate', status: 'active', icon: '✎', params: ['action', 'path', 'text'] },
      { id: 'folders', name: 'Folder Profiles', endpoint: 'GET /folders', desc: 'List and manage watched folders', status: 'active', icon: '📁', params: [] },
    ],
  },
  communication: {
    label: 'Communication',
    icon: '✉',
    aliases: ['comm', 'communications', 'chat'],
    apis: [
      { id: 'mattermost_send', name: 'Send Message', endpoint: 'POST /mattermost/send', desc: 'Send to a Mattermost channel', status: 'needs_key', icon: '→', params: ['channel', 'message'] },
      { id: 'mattermost_broadcast', name: 'Broadcast', endpoint: 'POST /mattermost/broadcast', desc: 'Send to all AI channels', status: 'needs_key', icon: '☊', params: ['message'] },
      { id: 'mattermost_unread', name: 'Unread Count', endpoint: 'GET /mattermost/unread', desc: 'Check unread per channel', status: 'needs_key', icon: '#', params: [] },
      { id: 'messages', name: 'Hub Messages', endpoint: 'GET /messages', desc: 'Read/write hub message stream', status: 'active', icon: '☰', params: ['limit'] },
      { id: 'clipboard', name: 'Clipboard', endpoint: 'POST /clipboard/save', desc: 'Save/push clipboard content', status: 'active', icon: '⧉', params: ['text'] },
    ],
  },
  ai_models: {
    label: 'AI Models',
    icon: '◎',
    aliases: ['ai', 'models', 'model'],
    apis: [
      { id: 'openai', name: 'OpenAI', endpoint: 'External', desc: 'GPT, embeddings, agents', status: 'needs_key', icon: '◌', env: 'OPENAI_API_KEY', docs: 'https://platform.openai.com/docs' },
      { id: 'anthropic', name: 'Anthropic', endpoint: 'External', desc: 'Claude API', status: 'needs_key', icon: '◍', env: 'ANTHROPIC_API_KEY' },
      { id: 'gemini', name: 'Google Gemini', endpoint: 'External', desc: 'Deep research, NotebookLM', status: 'needs_key', icon: '✦', env: 'GEMINI_API_KEY', docs: 'https://gemini.google.com' },
      { id: 'deepseek', name: 'DeepSeek', endpoint: 'External', desc: 'Station 17 pipeline', status: 'needs_key', icon: '◆', env: 'DEEPSEEK_API_KEY' },
      { id: 'ollama', name: 'Ollama', endpoint: 'http://192.168.2.50:11434', desc: 'Local LLM inference', status: 'offline', icon: '●' },
      { id: 'notebooklm', name: 'NotebookLM', endpoint: 'External', desc: 'Research notebooks and source packs', status: 'needs_key', icon: '▤', docs: 'https://notebooklm.google.com' },
    ],
  },
  nlp: {
    label: 'NLP Pipeline',
    icon: '∑',
    aliases: ['nlp', 'semantic'],
    apis: [
      { id: 'backside_nlp', name: 'BACKSIDE NLP', endpoint: 'http://192.168.2.50:8700', desc: 'Local model API (SBERT, DeBERTa, BART)', status: 'offline', icon: 'β' },
      { id: 'intelligence', name: 'Intelligence', endpoint: 'GET /intelligence/files', desc: 'File records and folder summaries', status: 'active', icon: 'ℹ', params: ['q'] },
      { id: 'semantic', name: 'Semantic Search', endpoint: 'POST /semantic/search', desc: 'Vector similarity search', status: 'configured', icon: '⌕', params: ['query'] },
      { id: 'fis_classify_nlp', name: 'Classify File', endpoint: 'POST /fis/classify', desc: 'Domain classification via FIS', status: 'configured', icon: '◇', params: ['file_path'] },
    ],
  },
  storage: {
    label: 'Storage',
    icon: '▰',
    aliases: ['storage', 'store'],
    apis: [
      { id: 'synology', name: 'Synology NAS', endpoint: 'http://192.168.2.50:5000', desc: 'NAS storage and Docker management', status: 'offline', icon: '▥' },
      { id: 'r2', name: 'Cloudflare R2', endpoint: 'External', desc: 'Media bucket storage', status: 'needs_key', icon: '☁', env: 'R2 keys', docs: 'https://developers.cloudflare.com/r2/' },
      { id: 'postgres', name: 'PostgreSQL', endpoint: '192.168.2.50:5432', desc: 'Axiom database, canonical nodes', status: 'offline', icon: '⬢' },
      { id: 'syncthing', name: 'Syncthing', endpoint: 'http://127.0.0.1:8384', desc: 'File sync between machines', status: 'offline', icon: '↔' },
      { id: 'cloudflare', name: 'Cloudflare', endpoint: 'External', desc: 'Pages deploys, DNS, and R2 console', status: 'needs_key', icon: '☁', env: 'CLOUDFLARE_API_TOKEN', docs: 'https://dash.cloudflare.com' },
    ],
  },
  desktop: {
    label: 'Desktop Control',
    icon: '⌨',
    aliases: ['desktop', 'control', 'operator'],
    apis: [
      { id: 'ahk_bridge', name: 'AHK Bridge', endpoint: 'POST /bridge/jobs', desc: 'Paste, send, overlay control', status: 'active', icon: '⌨', env: 'AHK_BRIDGE_URL', params: ['action', 'payload'] },
      { id: 'commands', name: 'Commands', endpoint: 'POST /operator/commands', desc: 'Execute shell commands with review', status: 'active', icon: '>', params: ['command'] },
      { id: 'agents', name: 'Agent Send', endpoint: 'POST /agents/send', desc: 'Route messages to AI agents', status: 'active', icon: '◎', params: ['target', 'message'] },
    ],
  },
};

const flattenApiRegistry = (cats) => Object.entries(cats).flatMap(([categoryId, category]) => category.apis.map((api) => ({ ...api, categoryId, category: category.label })));
const apiRegistryItems = flattenApiRegistry(apiRegistryCategories);

function loadCustomApis() {
  try { const saved = JSON.parse(localStorage.getItem(API_REGISTRY_KEY) || '[]'); return Array.isArray(saved) ? saved : []; } catch { return []; }
}

function endpointParts(endpoint = '') {
  const match = endpoint.match(/^(GET|POST|PATCH|PUT|DELETE)\s+(.+)$/i);
  return match ? { method: match[1].toUpperCase(), path: match[2] } : { method: 'EXTERNAL', path: endpoint };
}

function ApiShelfPanel({ setNotice }) {
  const [customApis, setCustomApis] = useState(loadCustomApis);
  const [selectedCategory, setSelectedCategory] = useState('file_system');
  const [selectedId, setSelectedId] = useState('fis_intake');
  const [filter, setFilter] = useState('');
  const [tryBody, setTryBody] = useState('{}');
  const [urlFormOpen, setUrlFormOpen] = useState(false);
  const [urlDraft, setUrlDraft] = useState('');
  const allItems = [...apiRegistryItems, ...customApis];
  const visibleItems = allItems.filter((item) => (selectedCategory === 'all' || item.categoryId === selectedCategory) && [item.name, item.category, item.status, item.endpoint, item.desc].join(' ').toLowerCase().includes(filter.toLowerCase()));
  const selected = allItems.find((item)=>item.id===selectedId) || visibleItems[0] || allItems[0];
  const parts = endpointParts(selected?.endpoint);
  const saveCustom = (next) => { setCustomApis(next); localStorage.setItem(API_REGISTRY_KEY, JSON.stringify(next)); };
  const copyApi = async (api = selected) => {
    const text = JSON.stringify({ id: api.id, name: api.name, category: api.category, status: api.status, endpoint: api.endpoint, description: api.desc, parameters: api.params || [], env: api.env || '', docs: api.docs || '' }, null, 2);
    await navigator.clipboard?.writeText?.('```json\n' + text + '\n```');
    setNotice(`Copied ${api.name} API spec.`);
  };
  const addUrlApi = () => {
    const url = urlDraft.trim();
    if (!url) return;
    const id = `custom-${Date.now()}`;
    let host = 'Imported API';
    try { host = new URL(url).hostname || host; } catch { host = url.replace(/^https?:\/\//, '').split('/')[0] || host; }
    const api = { id, name: host, categoryId: 'custom', category: 'Imported', status: 'needs_key', endpoint: url, desc: 'Imported docs/spec URL — extraction pending', icon: '+', docs: url, params: [] };
    saveCustom([...customApis, api]);
    setSelectedCategory('all'); setSelectedId(id); setUrlDraft(''); setUrlFormOpen(false); setNotice('Added API URL card. Auto-extraction is next.');
  };
  const copyVisibleApis = async () => {
    const text = JSON.stringify(visibleItems.map((api) => ({ id: api.id, name: api.name, category: api.category, status: api.status, endpoint: api.endpoint, description: api.desc, parameters: api.params || [] })), null, 2);
    await navigator.clipboard?.writeText?.('```json\n' + text + '\n```');
    setNotice(`Copied ${visibleItems.length} API specs.`);
  };
  const tryEndpoint = async () => {
    try {
      if (!parts.path?.startsWith('/')) throw new Error('External endpoint; open docs instead.');
      const body = parts.method === 'GET' ? undefined : JSON.parse(tryBody || '{}');
      const result = await topOfMindApi.requestRaw(parts.path, { method: parts.method, ...(body ? { body: JSON.stringify(body) } : {}) });
      setNotice(`${selected.name}: ${result?.status || 'request completed'}`);
    } catch (e) { setNotice(`${selected.name}: ${e.message}`); }
  };
  return <section className="tm-page api-registry-page">
    <div className="tm-page-head">
      <div>
        <h1>API Registry</h1>
        <p>Browse hub routes, external connectors, local models, storage, and desktop controls.</p>
      </div>
      <div className="tm-head-actions">
        <button className="tm-primary" onClick={()=>setUrlFormOpen(!urlFormOpen)}>＋ Add API from URL</button>
        <button className="tm-secondary" onClick={copyVisibleApis}>Copy visible APIs</button>
        <button className="tm-secondary" onClick={()=>copyApi(selected)}>Copy selected</button>
      </div>
    </div>

    {urlFormOpen && <div className="tm-url-bar"><input value={urlDraft} onChange={(e)=>setUrlDraft(e.target.value)} placeholder="https://example.com/openapi.json or docs page"/><button className="tm-primary" onClick={addUrlApi}>Create card</button></div>}

    <div className="tm-api-shell">
      <aside className="tm-api-sidebar">
        <div className="tm-side-section">Store</div>
        <button className={selectedCategory==='all'?'selected':''} onClick={()=>setSelectedCategory('all')}><span className="tm-side-icon">⌘</span><span>All APIs</span><b>{allItems.length}</b></button>
        <div className="tm-side-section">Categories</div>
        {Object.entries(apiRegistryCategories).map(([id, cat])=><button key={id} className={selectedCategory===id?'selected':''} onClick={()=>setSelectedCategory(id)}><span className="tm-side-icon">{cat.icon}</span><span>{cat.label}</span><b>{cat.apis.length}</b></button>)}
        {customApis.length > 0 && <><div className="tm-side-section">Installed</div><button className={selectedCategory==='custom'?'selected':''} onClick={()=>setSelectedCategory('custom')}><span className="tm-side-icon">＋</span><span>Imported</span><b>{customApis.length}</b></button></>}
        <div className="tm-side-card"><strong>{visibleItems.length}</strong><span>visible APIs</span><small>Green = active/configured · amber = needs key · red = offline</small></div>
      </aside>

      <section className="tm-api-main">
        <div className="tm-toolbar">
          <div className="tm-search"><span>⌕</span><input value={filter} onChange={(e)=>setFilter(e.target.value)} placeholder="Search APIs, endpoints, parameters…"/></div>
          <button className="tm-icon-button" title="Grid view">▦</button>
          <button className="tm-sort">↕ Status</button>
        </div>
        <div className="tm-card-grid">
          {visibleItems.map((api)=><article key={api.id} className={`tm-api-card ${selected?.id===api.id?'selected':''}`} onClick={()=>setSelectedId(api.id)}>
            <div className="tm-card-body">
              <span className="tm-api-avatar">{api.icon || '◆'}</span>
              <div className="tm-card-copy">
                <div className="tm-card-title"><b>{api.name}</b><span className={`tm-dot ${api.status}`}></span></div>
                <p>{api.desc}</p>
                <code>{api.endpoint}</code>
              </div>
              <span className={`api-status ${api.status}`}>{(api.status || 'offline').replace('_',' ')}</span>
            </div>
            <div className="tm-card-footer">
              <button onClick={(e)=>{e.stopPropagation(); copyApi(api);}}>⧉ Copy</button>
              <button onClick={(e)=>{e.stopPropagation(); setSelectedId(api.id); setTryBody(JSON.stringify(Object.fromEntries((api.params || []).map((param)=>[param, ''])), null, 2));}}>Use now</button>
            </div>
          </article>)}
        </div>
      </section>

      <aside className="tm-api-detail">
        {selected ? <>
          <div className="tm-detail-head"><span className="tm-api-avatar large">{selected.icon || '◆'}</span><div><h2>{selected.name}</h2><p>{selected.category} · {selected.status}</p></div></div>
          <div className="tm-tabs"><button className="active">Overview</button><button>Parameters</button><button>Try it</button></div>
          <dl className="tm-meta"><dt>Endpoint</dt><dd><code>{selected.endpoint || ''}</code></dd><dt>Description</dt><dd>{selected.desc}</dd><dt>Parameters</dt><dd>{(selected.params || []).length ? (selected.params || []).join(', ') : 'None listed'}</dd><dt>Env / key</dt><dd>{selected.env || 'Not required or managed externally'}</dd></dl>
          <label className="tm-try-label">Try it body<textarea value={tryBody} onChange={(e)=>setTryBody(e.target.value)} placeholder='{"path":"D:/..."}'/></label>
          <div className="tm-detail-actions"><button className="tm-primary" onClick={tryEndpoint}>Try endpoint</button><button className="tm-secondary" onClick={()=>copyApi(selected)}>Copy API</button>{selected.docs && <button className="tm-secondary" onClick={()=>window.open(selected.docs, '_blank', 'noopener')}>Open docs</button>}</div>
          <small className="api-hint">GET routes ignore the body. External endpoints are copied/opened as context only.</small>
        </> : <p>Select an API card.</p>}
      </aside>
    </div>
  </section>;
}

// ---- Theme helpers (void black default; slate restores original look) ----
const THEME_KEY = 'topOfMind.theme';
const FONT_KEY = 'topOfMind.fontSize';
function applyThemeFromStorage() {
  const theme = localStorage.getItem(THEME_KEY) || 'void';
  document.body.classList.toggle('theme-void', theme !== 'slate');
  document.body.classList.toggle('theme-slate', theme === 'slate');
  const font = localStorage.getItem(FONT_KEY) || 'standard';
  document.documentElement.style.fontSize = font === 'compact' ? '14px' : font === 'large' ? '18px' : '16px';
}

// ---- Sidebar (unchanged) ----

function Sidebar({ folders, selectedFolder, setSelectedFolder, createFolder, active, setActive }) {
  const sections = globalNavItems.map((item) => item.id);
  const [collapsed, setCollapsed] = useState({});
  const [folderMeta, setFolderMeta] = useState(() => { try { return JSON.parse(localStorage.getItem('topOfMind.folderMeta.v1') || '{}'); } catch { return {}; } });
  const [systemOpen, setSystemOpen] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState(() => localStorage.getItem('topOfMind.systemPrompt') || 'You are David OS: concise, structured, and action oriented.');
  const [searchVars, setSearchVars] = useState({ date: new Date().toISOString().slice(0, 10), time: 'now', size: 'balanced', mode: 'semantic' });
  const workspaceItems = ['Markdown note', 'Clipboard capture', 'Prompt snippet', 'Chat thread'];
  const saveSystemPrompt = () => { localStorage.setItem('topOfMind.systemPrompt', systemPrompt); setSystemOpen(false); };
  const persistFolderMeta = (next) => { setFolderMeta(next); localStorage.setItem('topOfMind.folderMeta.v1', JSON.stringify(next)); };
  const toggleFolder = (id) => setCollapsed((c) => ({ ...c, [id]: !c[id] }));
  const toggleFolderStar = (id) => persistFolderMeta({ ...folderMeta, [id]: { ...(folderMeta[id] || {}), starred: !folderMeta[id]?.starred } });
  const editFolderTags = (id) => { const tags = prompt('Folder tags, comma separated', (folderMeta[id]?.tags || []).join(', ')); if (tags === null) return; persistFolderMeta({ ...folderMeta, [id]: { ...(folderMeta[id] || {}), tags: tags.split(',').map((tag)=>tag.trim()).filter(Boolean) } }); };
  const renderFolder = (f, depth = 0) => {
    const id = f.id || f.folder_id || f.folder_code || f.name;
    const children = f.children || [];
    const isCollapsed = collapsed[id];
    const selected = selectedFolder && (selectedFolder.id || selectedFolder.folder_id || selectedFolder.folder_code || selectedFolder.name) === id;
    const meta = folderMeta[id] || {};
    return <div key={id} className="folder-node">
      <div className={`folder-row ${selected ? 'selected' : ''}`} style={{'--depth': depth}}>
        <button className="folder-caret" onClick={()=>toggleFolder(id)} aria-label={isCollapsed ? 'Expand folder' : 'Collapse folder'}>{children.length ? (isCollapsed ? '▸' : '▾') : '·'}</button>
        <button className="folder-name" onClick={()=>setSelectedFolder(f)}>📁 <span>{f.name || f.title}</span> <small>{f.folder_code || children.length}</small></button>
        <button className={`folder-star ${meta.starred ? 'starred' : ''}`} onClick={()=>toggleFolderStar(id)} title={meta.starred ? 'Unstar folder' : 'Star folder'}>{meta.starred ? '★' : '☆'}</button>
        <button className="folder-tags" onClick={()=>editFolderTags(id)} title="Edit folder tags">#</button>
        <button className="folder-plus" onClick={createFolder} title="Add nested folder or item">＋</button>
      </div>
      {meta.tags?.length > 0 && <div className="folder-tag-list" style={{'--depth': depth + 1}}>{meta.tags.map((tag)=><span key={tag}>#{tag}</span>)}</div>}
      {!isCollapsed && <div>
        {children.map((c)=>renderFolder(c, depth + 1))}
        {depth < 2 && workspaceItems.slice(0, depth === 0 ? 2 : 1).map((item)=><button key={`${id}-${item}`} className="chat asset-item" style={{'--depth': depth + 1}}>▣ {item}</button>)}
      </div>}
    </div>;
  };
  return <aside className="sidebar">
    <div className="sidebar-top">
      <button className="new">＋ New Chat</button>
      <button className="system-prompt-button" onClick={()=>setSystemOpen(true)} title="Open system prompt">☉</button>
    </div>
    <input className="search" placeholder="Search chats, folders, markdown, clipboards"/>
    <div className="search-vars" aria-label="Search variables">
      <label>Date<input type="date" value={searchVars.date} onChange={(e)=>setSearchVars({...searchVars, date:e.target.value})}/></label>
      <label>Time<select value={searchVars.time} onChange={(e)=>setSearchVars({...searchVars, time:e.target.value})}><option>now</option><option>today</option><option>week</option><option>custom</option></select></label>
      <label>Size<select value={searchVars.size} onChange={(e)=>setSearchVars({...searchVars, size:e.target.value})}><option>balanced</option><option>small</option><option>large</option></select></label>
      <label>Mode<select value={searchVars.mode} onChange={(e)=>setSearchVars({...searchVars, mode:e.target.value})}><option>semantic</option><option>exact</option><option>recent</option></select></label>
    </div>
    <div className="folder-heading"><h3>Folders</h3><button onClick={createFolder}>＋ Folder</button></div>
    {folders.map((f)=>renderFolder(f))}
    <h3>Navigation</h3>
    {sections.map((s)=><button key={s} onClick={()=>setActive(s)} className={`row ${active===s?'selected':''}`}>◇ {s}</button>)}
    {systemOpen && <div className="modal-backdrop" onClick={()=>setSystemOpen(false)}><section className="system-modal" onClick={(e)=>e.stopPropagation()}><h2>System Prompt</h2><p>Tune the outside instruction layer before you chat or launch prompts.</p><textarea value={systemPrompt} onChange={(e)=>setSystemPrompt(e.target.value)}/><div><button onClick={()=>setSystemOpen(false)}>Cancel</button><button className="tm-primary" onClick={saveSystemPrompt}>Save prompt</button></div></section></div>}
  </aside>;
}

// ---- Funnel (source control) ----
function Funnel({ sources, setSources, selectedMessage, patchMessage, collapsed, setCollapsed, activeAgentId, setActiveAgentId }) {
  const toggle = (id, key) => setSources((ss)=>ss.map((s)=> (s.id||s.name)===id ? {...s, [key]: !s[key], status: key==='paused' ? 'paused' : s.status} : s));
  const assign = (field, value) => selectedMessage && patchMessage(selectedMessage.id || selectedMessage.message_id, { [field]: value });
  return <aside className={`funnel ${collapsed?'collapsed':''}`}><button onClick={()=>setCollapsed(!collapsed)}>{collapsed?'▶':'◀'}</button>{!collapsed && <><h3>Funnel</h3>{sources.map((s)=>{ const id = srcId(s); const isActive = id === activeAgentId; return <div className={`source ${isActive?'active-source':''}`} key={id} onClick={()=>setActiveAgentId(id)} role="button" tabIndex="0" onKeyDown={(e)=>{if(e.key==='Enter'||e.key===' ') setActiveAgentId(id);}}><span className="avatar">{initials(s)}</span><b>{srcName(s)}</b><em>{isActive ? 'active' : (s.status||'online')}</em><button onClick={(e)=>{e.stopPropagation();toggle(id,'paused');}}>pause</button><button onClick={(e)=>{e.stopPropagation();toggle(id,'muted');}}>mute</button><label onClick={(e)=>e.stopPropagation()}><input type="checkbox" defaultChecked/> include</label><small>priority {s.priority || s.priority_code || 'normal'} · {s.configured === false ? 'not configured' : 'configured'}</small></div>})}<h3>Assign selected</h3><button onClick={()=>assign('wall_code', NUMBERING.walls.main)}>Main wall</button><button onClick={()=>assign('wall_code', NUMBERING.walls.code)}>Code wall</button><button onClick={()=>assign('folder_code', NUMBERING.folders.active)}>Active folder</button><div className="grid"><button onClick={()=>topOfMindApi.combine({})}>combine</button><button>split draft</button><button>broadcast draft</button><button onClick={()=>topOfMindApi.endAll()}>end all</button></div></>}</aside>;
}

// ---- Operator Surface (unchanged from original) ----
const operationFamilies = [
  { id: 'ahk', label: 'AHK', icon: '⌨', group: 'AutoHotkey' },
  { id: 'clipboard', label: 'Clipboard', icon: '⧉', group: 'Clipboard' },
  { id: 'files', label: 'Files', icon: '▣', group: 'File Operations' },
  { id: 'knowledge', label: 'Knowledge', icon: '◇', group: 'Knowledge Bank' },
  { id: 'vector', label: 'Vector', icon: '∑', group: 'Vectorization' },
  { id: 'commands', label: 'Commands', icon: '>', group: 'Command Line' },
  { id: 'agents', label: 'Agents', icon: '◎', group: 'Agents' },
  { id: 'memory', label: 'Memory', icon: '◈', group: 'Memory' },
  { id: 'hub', label: 'Hub', icon: '◆', group: 'API Calls' },
];

function OperatorSurface({ selectedSource, input, setNotice, setSources }) {
  const [family, setFamilyState] = useState(()=>localStorage.getItem(OP_FAMILY_KEY) || 'hub');
  const [folded, setFolded] = useState(false);
  const [capabilities, setCapabilities] = useState([]);
  const [ahkOnline, setAhkOnline] = useState(false);
  const [profile, setProfile] = useState('TopMind');
  const [builderOpen, setBuilderOpen] = useState(false);
  const [builderTab, setBuilderTab] = useState('agent');
  const [agentDraft, setAgentDraft] = useState({ name: '', role: 'Research assistant', model: 'Claude Opus 4.6', tags: 'custom' });
  const [apiDraft, setApiDraft] = useState({ name: '', endpoint: '', tags: 'custom' });
  const agent = { id: srcId(selectedSource), name: srcName(selectedSource), source_code: selectedSource?.source_code };
  const selectedFamily = operationFamilies.find((f)=>f.id===family) || operationFamilies[0];
  const setFamily = (id) => { setFamilyState(id); localStorage.setItem(OP_FAMILY_KEY, id); setFolded(false); };
  const status = (name, text) => setNotice(`${name}: ${text}`);
  const bridgeJob = (action, payload = {}) => topOfMindApi.createBridgeJob({ worker: 'ahk-main', action, target: agent, payload, source: 'operator-surface' });
  const createCustomAgent = () => {
    const name = agentDraft.name.trim() || agentDraft.role;
    const customAgent = { id: `custom-agent-${Date.now()}`, name, label: name, source_id: name.toLowerCase().replace(/[^a-z0-9]+/g, '-'), status: 'online', configured: true, template: agentDraft.role, model: agentDraft.model, tags: agentDraft.tags.split(',').map((tag)=>tag.trim()).filter(Boolean) };
    const saved = [...(JSON.parse(localStorage.getItem(CUSTOM_AGENTS_KEY) || '[]')), customAgent];
    localStorage.setItem(CUSTOM_AGENTS_KEY, JSON.stringify(saved));
    setSources((items)=>[...items, customAgent]);
    setNotice(`Created custom agent: ${name}`);
    setBuilderOpen(false);
  };
  const createCustomApi = () => {
    const name = apiDraft.name.trim() || apiDraft.endpoint.trim() || 'Custom API';
    const customApi = { id: `custom-${Date.now()}`, name, categoryId: 'custom', category: 'Imported', status: 'needs_key', endpoint: apiDraft.endpoint.trim() || 'External', desc: `Custom API · tags: ${apiDraft.tags}`, icon: '+', docs: apiDraft.endpoint.trim(), params: [] };
    const saved = loadCustomApis();
    localStorage.setItem(API_REGISTRY_KEY, JSON.stringify([...saved, customApi]));
    setNotice(`Added custom API: ${name}`);
    setBuilderOpen(false);
  };
  async function safeCall(name, fn, options = {}) {
    if (options.confirm && !window.confirm(options.confirm)) { status(name, 'cancelled'); return; }
    try { const result = await fn(); status(name, result?.status || result?.message || 'hub request accepted'); }
    catch (e) { status(name, `API route unavailable or failed (${e.message})`); }
  }
  useEffect(()=>{ topOfMindApi.getCapabilities().then((d)=>setCapabilities(arr(d,'capabilities'))).catch(()=>setCapabilities([])); },[]);
  const groupedCapabilities = capabilities.filter((cap)=>cap.enabled !== false && (cap.ui_group || '').toLowerCase() === selectedFamily.group.toLowerCase());
  const actionButton = (label, onClick, danger) => <button className={danger?'danger':''} onClick={onClick}>{label}</button>;
  const defaultActions = {
    ahk: [
      actionButton('Paste job', ()=>safeCall('AHK Paste', ()=>bridgeJob('paste_to_active', { text: input }))),
      actionButton('Send job', ()=>safeCall('AHK Send', ()=>bridgeJob('send_to_active', { text: input }))),
      actionButton('Toggle overlay', ()=>safeCall('AHK Overlay', ()=>bridgeJob('toggle_overlay', { profile }))),
    ],
    clipboard: [
      actionButton('Save clipboard', ()=>safeCall('Clipboard', ()=>topOfMindApi.saveClipboard({ action: 'clipboard_save', target: agent, text: input, dry_run: true }))),
      actionButton('Push clipboard', ()=>safeCall('Push', ()=>topOfMindApi.pushClipboard({ target: agent, message: input, dry_run: true }))),
    ],
    files: [
      actionButton('List folders', ()=>safeCall('Folders', ()=>topOfMindApi.getFolders())),
      actionButton('Dry-run file action', ()=>safeCall('File dry-run', ()=>topOfMindApi.fileActions({ action: 'dry_run', target: agent, dry_run: true }))),
      actionButton('Overwrite file', ()=>safeCall('Overwrite', ()=>topOfMindApi.fileActions({ action: 'overwrite_file', target: agent, dry_run: true }), { confirm: 'Overwrite file actions require confirmation. Continue dry-run?' }), true),
    ],
    knowledge: [actionButton('Search KB', ()=>safeCall('Knowledge', ()=>topOfMindApi.searchFileCache(input || '')))],
    vector: [
      actionButton('Embed pending', ()=>safeCall('Vector', ()=>topOfMindApi.embedPending())),
      actionButton('Search vectors', ()=>safeCall('Vector Search', ()=>topOfMindApi.searchMemory(input || '', 'vector'))),
      actionButton('Bulk import', ()=>safeCall('Bulk import', ()=>bridgeJob('bulk_import', { dry_run: true }), { confirm: 'Bulk import requires confirmation. Queue dry-run?' }), true),
    ],
    commands: [
      actionButton('Dry-run command', ()=>safeCall('Command', ()=>topOfMindApi.command({ action: 'dry_run', command: input, dry_run: true }), { confirm: 'Command line actions require confirmation. Continue dry-run?' }), true),
    ],
    agents: [
      actionButton('Agent send', ()=>safeCall('Agent Send', ()=>topOfMindApi.sendAgent({ action: 'agent_send', target: agent, message: input, route_only: true, dry_run: true }))),
      actionButton('Broadcast dry-run', ()=>safeCall('Broadcast', ()=>topOfMindApi.sendAgent({ action: 'broadcast_all', target: agent, message: input, route_only: true, dry_run: true }), { confirm: 'Broadcast to all agents requires confirmation. Continue dry-run?' }), true),
    ],
    memory: [
      actionButton('Save memory', ()=>safeCall('Memory', ()=>topOfMindApi.createMemoryItem({ text: input, source: agent, dry_run: true }))),
      actionButton('Search memory', ()=>safeCall('Memory Search', ()=>topOfMindApi.searchMemory(input || ''))),
    ],
    hub: [
      actionButton('Health', ()=>safeCall('Hub Health', ()=>topOfMindApi.hubHealth())),
      actionButton('Capabilities', ()=>safeCall('Capabilities', async()=>{ const d = await topOfMindApi.getCapabilities(); setCapabilities(arr(d,'capabilities')); return d; })),
      actionButton('End all', ()=>safeCall('End All', ()=>topOfMindApi.endAll({ action: 'end_all', target: agent }), { confirm: 'Stop/end all active jobs?' }), true),
    ],
  };
  return <aside className={`operator-surface ${folded?'folded':''}`} aria-label="Operator command surface">
    <nav className="shortcut-rail" aria-label="Operation shortcuts">
      <button className="fold" onClick={()=>setFolded(!folded)} aria-label={folded?'Expand operations':'Fold operations'} title={folded?'Expand operations':'Fold operations'}>{folded?'◀':'▶'}</button>
      <div className="rail-ahk" aria-label="Persistent AutoHotkey controls">
        <span className={`dot ${ahkOnline?'ok':'bad'}`} title={`AHK ${ahkOnline?'online':'offline'} · ${profile}`}></span>
        <button onClick={()=>safeCall('AHK Frame', ()=>bridgeJob('toggle_overlay', { profile }))} aria-label="Toggle AHK frame overlay" title="Frame / overlay">F</button>
        <button onClick={()=>safeCall('AHK Paste', ()=>bridgeJob('paste_to_active', { text: input }))} aria-label="AHK paste to active" title="Paste">P</button>
        <button onClick={()=>safeCall('AHK Send', ()=>bridgeJob('send_to_active', { text: input }))} aria-label="AHK send to active" title="Send">S</button>
        <button onClick={()=>safeCall('End All', ()=>topOfMindApi.endAll({ action: 'end_all', target: agent }))} aria-label="Stop or end all" title="Stop / end all">!</button>
        <button onClick={()=>safeCall('Hub', ()=>topOfMindApi.hubHealth())} aria-label="Hub health" title="Hub health">H</button>
        <button onClick={()=>safeCall('Bridge Test', async()=>{ const r = await bridgeJob('bridge_test', { profile }); setAhkOnline(true); return r; })} aria-label="Quick bridge test" title="Bridge test">T</button>
      </div>
      {operationFamilies.map((item)=><button key={item.id} className={family===item.id?'active':''} onClick={()=>setFamily(item.id)} aria-label={item.label} title={item.label}>{item.icon}</button>)}
    </nav>
    {!folded && <section className="ops-panel">
      <div className="builder-card">
        <button className="builder-plus" onClick={()=>setBuilderOpen(!builderOpen)}>＋ Add agent / API</button>
        {builderOpen && <div className="builder-form">
          <div className="builder-tabs"><button className={builderTab==='agent'?'active':''} onClick={()=>setBuilderTab('agent')}>Agent template</button><button className={builderTab==='api'?'active':''} onClick={()=>setBuilderTab('api')}>API card</button></div>
          {builderTab === 'agent' ? <div className="builder-fields">
            <input value={agentDraft.name} onChange={(e)=>setAgentDraft({...agentDraft, name:e.target.value})} placeholder="Agent name"/>
            <select value={agentDraft.role} onChange={(e)=>setAgentDraft({...agentDraft, role:e.target.value})}><option>Research assistant</option><option>Life coach</option><option>Code partner</option><option>Day trading analyst</option><option>Workbook builder</option></select>
            <input value={agentDraft.model} onChange={(e)=>setAgentDraft({...agentDraft, model:e.target.value})} placeholder="Default model"/>
            <input value={agentDraft.tags} onChange={(e)=>setAgentDraft({...agentDraft, tags:e.target.value})} placeholder="tags"/>
            <button className="tm-primary" onClick={createCustomAgent}>Create agent</button>
          </div> : <div className="builder-fields">
            <input value={apiDraft.name} onChange={(e)=>setApiDraft({...apiDraft, name:e.target.value})} placeholder="API name"/>
            <input value={apiDraft.endpoint} onChange={(e)=>setApiDraft({...apiDraft, endpoint:e.target.value})} placeholder="https://... or POST /route"/>
            <input value={apiDraft.tags} onChange={(e)=>setApiDraft({...apiDraft, tags:e.target.value})} placeholder="tags"/>
            <button className="tm-primary" onClick={createCustomApi}>Add API</button>
          </div>}
        </div>}
      </div>
      <div className="ahk-layer" aria-label="Persistent AutoHotkey layer">
        <div><b>AHK</b><span className={`dot ${ahkOnline?'ok':'bad'}`}></span></div>
        <small>{ahkOnline?'online':'offline'} · {profile}</small>
        <div className="mini-grid">
          <button onClick={()=>safeCall('AHK Frame', ()=>bridgeJob('toggle_overlay', { profile }))}>Frame</button>
          <button onClick={()=>safeCall('AHK Paste', ()=>bridgeJob('paste_to_active', { text: input }))}>Paste</button>
          <button onClick={()=>safeCall('AHK Send', ()=>bridgeJob('send_to_active', { text: input }))}>Send</button>
          <button onClick={()=>safeCall('End All', ()=>topOfMindApi.endAll({ action: 'end_all', target: agent }))}>Stop</button>
          <button onClick={()=>safeCall('Hub', ()=>topOfMindApi.hubHealth())}>Hub</button>
          <button onClick={()=>safeCall('Bridge Test', async()=>{ const r = await bridgeJob('bridge_test', { profile }); setAhkOnline(true); return r; })}>Test</button>
        </div>
      </div>
      <div className="ops-head"><b>{selectedFamily.group}</b><small>target: {agent.name}</small></div>
      {groupedCapabilities.length ? <div className="cap-list">{groupedCapabilities.map((cap)=><button key={cap.id} disabled={cap.enabled===false} className={cap.requires_confirm || cap.risk_level === 'danger' ? 'danger' : ''} onClick={()=>safeCall(cap.label, ()=>topOfMindApi.createBridgeJob({ worker: 'ahk-main', action: cap.id, target: agent, payload: { dry_run: cap.supports_dry_run !== false }, source: 'capability' }), cap.requires_confirm ? { confirm: `${cap.label} requires confirmation. Continue?` } : {})}>{cap.label}<small>{cap.capability} · {cap.risk_level || 'safe'}</small></button>)}</div> : <div className="ops-grid">{defaultActions[family] || defaultActions.hub}<small className="placeholder">No /capabilities data for this group yet; showing safe hub placeholders.</small></div>}
    </section>}
  </aside>;
}

// ---- Search panels (unchanged) ----
function SearchPanel({ title, modeToggle, onSearch }) {
  const [q, setQ] = useState(''); const [mode, setMode] = useState('text'); const [results, setResults] = useState([]);
  async function run(){ try { setResults(arr(await onSearch(q, mode), 'items')); } catch { setResults([{ name: 'API offline', content: 'Search could not run.' }]); } }
  return <section className="panel"><h3>{title}</h3><div className="inline"><input value={q} onChange={(e)=>setQ(e.target.value)} placeholder="Search…"/>{modeToggle && <label><input type="checkbox" onChange={(e)=>setMode(e.target.checked?'vector':'text')}/> vector</label>}<button onClick={run}>Search</button></div>{results.slice(0,8).map((r,i)=><p key={i}>▣ {r.name || r.path || r.title || r.content || JSON.stringify(r)}</p>)}</section>;
}

// ============================================================
// MAIN APP
// ============================================================
function CommandPalette({ open, onClose, setActive, setInput, sources, folders, setNotice }) {
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const [favorites, setFavorites] = useState(() => { try { return JSON.parse(localStorage.getItem(COMMAND_FAVORITES_KEY) || '[]'); } catch { return []; } });
  const [recents, setRecents] = useState(() => { try { return JSON.parse(localStorage.getItem(COMMAND_RECENTS_KEY) || '[]'); } catch { return []; } });
  const actions = useMemo(() => {
    const staticActions = [
      { id: 'nav.chats', title: 'Open chats', description: 'Go to the message relay and composer.', category: 'Navigation', permissions: ['read:messages'], handler: () => setActive('chats') },
      { id: 'nav.clipboard', title: 'Open clipboard workspace', description: 'Search, merge, pin, restore, export, and send clipboard records.', category: 'Navigation', permissions: ['read:clipboard'], handler: () => setActive('clipboard') },
      { id: 'nav.prompts', title: 'Open prompts', description: 'Browse prompt library and slash prompt source.', category: 'Navigation', permissions: ['read:prompts'], handler: () => setActive('prompts') },
      { id: 'nav.apis', title: 'Open API registry', description: 'Browse API cards and imported integrations.', category: 'Navigation', permissions: ['read:apis'], handler: () => setActive('apis') },
      { id: 'nav.files', title: 'Open files', description: 'Search the file cache.', category: 'Navigation', permissions: ['read:files'], handler: () => setActive('files') },
      { id: 'nav.memory', title: 'Open memory', description: 'Search durable memory.', category: 'Navigation', permissions: ['read:memory'], handler: () => setActive('memory') },
      { id: 'nav.operator', title: 'Open operator', description: 'Review-gated file and command drafts.', category: 'Navigation', permissions: ['review:mutations'], handler: () => setActive('operator') },
      { id: 'cmd.api-intake', title: 'Run /api filesystem intake', description: 'Prepare an intake command in the composer.', category: 'Command', parameters: ['source_folder'], permissions: ['create:job'], handler: () => { setActive('chats'); setInput('/api filesystem intake '); } },
      { id: 'cmd.api-neardup', title: 'Run /api filesystem neardup', description: 'Prepare duplicate scan command.', category: 'Command', permissions: ['create:job'], handler: () => { setActive('chats'); setInput('/api filesystem neardup'); } },
      { id: 'settings.api', title: 'API base URL settings', description: 'Configure local FastAPI endpoint.', category: 'Settings', permissions: ['configure:client'], handler: () => setActive('settings') },
    ];
    const sourceActions = (sources || []).map((source) => ({ id: `agent.${srcId(source)}`, title: `Chat with ${srcName(source)}`, description: 'Select this agent/source for the composer.', category: 'Agents', permissions: ['send:agent'], handler: () => { setActive('chats'); setNotice?.(`Select ${srcName(source)} from the funnel to make it active.`); } }));
    const folderActions = (folders || []).map((folder) => ({ id: `folder.${folder.id || folder.name}`, title: `Open folder ${folder.name}`, description: 'Folder result from the current workspace tree.', category: 'Folders', permissions: ['read:folders'], handler: () => setNotice?.(`Folder action available: ${folder.name}`) }));
    return [...staticActions, ...sourceActions, ...folderActions];
  }, [sources, folders, setActive, setInput, setNotice]);
  const matches = useMemo(() => {
    const hay = (action) => [action.title, action.description, action.category, ...(action.parameters || []), ...(action.permissions || [])].join(' ').toLowerCase();
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const ranked = actions.filter((action) => terms.every((term) => hay(action).includes(term)));
    return ranked.sort((a, b) => favorites.includes(b.id) - favorites.includes(a.id) || recents.indexOf(a.id) - recents.indexOf(b.id));
  }, [actions, query, favorites, recents]);
  useEffect(() => { if (!open) return; const onKey = (event) => { if (event.key === 'Escape') onClose(); if (event.key === 'ArrowDown') { event.preventDefault(); setCursor((value) => Math.min(value + 1, matches.length - 1)); } if (event.key === 'ArrowUp') { event.preventDefault(); setCursor((value) => Math.max(value - 1, 0)); } if (event.key === 'Enter' && matches[cursor]) { event.preventDefault(); run(matches[cursor]); } }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, [open, matches, cursor]);
  const persistFavorites = (next) => { setFavorites(next); localStorage.setItem(COMMAND_FAVORITES_KEY, JSON.stringify(next)); };
  const run = (action) => { action.handler(); const next = [action.id, ...recents.filter((id) => id !== action.id)].slice(0, 10); setRecents(next); localStorage.setItem(COMMAND_RECENTS_KEY, JSON.stringify(next)); onClose(); };
  if (!open) return null;
  return <div className="command-backdrop" role="dialog" aria-modal="true"><div className="command-palette"><input autoFocus value={query} onChange={(e) => { setQuery(e.target.value); setCursor(0); }} placeholder="Search chats, files, folders, clipboard, prompts, APIs, agents, models, plugins, workflows, settings…" /> <div className="command-list">{matches.map((action, index) => <div key={action.id} className={`command-row ${index === cursor ? 'active' : ''}`} onMouseEnter={() => setCursor(index)} onClick={() => run(action)}><button onClick={(e) => { e.stopPropagation(); persistFavorites(favorites.includes(action.id) ? favorites.filter((id) => id !== action.id) : [...favorites, action.id]); }}>{favorites.includes(action.id) ? '★' : '☆'}</button><div><b>{action.title}</b><p>{action.description}</p><small>{action.category} · permissions: {(action.permissions || []).join(', ') || 'none'} · params: {(action.parameters || []).join(', ') || 'none'}</small></div></div>)}</div>{!matches.length && <div className="tm-empty">No command matches.</div>}</div></div>;
}

function App() {
  const [sources, setSources] = useState(fallbackSources);
  const [folders, setFolders] = useState(starterFolders);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [active, setActive] = useState('chats');
  const [selectedFolder, setSelectedFolder] = useState(starterFolders[0]);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [online, setOnline] = useState(false);
  const [notice, setNotice] = useState('');
  const [funnelCollapsed, setFunnelCollapsed] = useState(false);
  const [activeAgentId, setActiveAgentIdState] = useState(()=>localStorage.getItem(ACTIVE_AGENT_KEY) || 'kimi');
  const [chatFilter, setChatFilter] = useState(null);
  const [commandOpen, setCommandOpen] = useState(false);

  const setActiveAgentId = (id) => { setActiveAgentIdState(id); localStorage.setItem(ACTIVE_AGENT_KEY, id); };

  useEffect(() => { applyThemeFromStorage(); }, []);

  useEffect(() => { const onKey = (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen(true); } }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, []);

  // Load messages on mount + polling (interval configurable in Settings → Workspace)
  useEffect(()=>{
    const pollMs = Math.max(1000, Number(localStorage.getItem('topOfMind.pollMs')) || 4000);
    topOfMindApi.getSources().then(d=>{const s=arr(d,'sources'); const custom = JSON.parse(localStorage.getItem(CUSTOM_AGENTS_KEY) || '[]'); if(s.length || custom.length) setSources([...s, ...custom]); setOnline(true);}).catch(e=>{const custom = JSON.parse(localStorage.getItem(CUSTOM_AGENTS_KEY) || '[]'); if(custom.length) setSources((current)=>[...current, ...custom]); setOnline(false); setNotice(e.message);});
    topOfMindApi.getFolders().then(d=>setFolders(arr(d,'folders'))).catch(()=>{});
    const loadMessages = () => topOfMindApi.getMessages(75).then(d=>{setMessages(arr(d,'messages')); setOnline(true);}).catch(()=>setOnline(false));
    loadMessages();
    const timer = setInterval(loadMessages, pollMs);
    return () => clearInterval(timer);
  },[]);

  const selectedSource = sources.find((source)=>srcId(source)===activeAgentId) || sources[0] || fallbackSources[0];

  async function runApiSlashCommand(text) {
    const tokens = text.match(/"[^"]*"|'[^']*'|\S+/g)?.map((token) => token.replace(/^['"]|['"]$/g, '')) || [];
    const [, category, action, ...args] = tokens;
    const cat = (category || '').toLowerCase();
    const act = (action || '').toLowerCase();
    const comm = cat === 'comm' || cat === 'communication';
    if ((cat === 'filesystem' || cat === 'file_system' || cat === 'fis') && act === 'intake') return topOfMindApi.fisIntake({ source_folder: args[0] || '' });
    if ((cat === 'filesystem' || cat === 'file_system' || cat === 'fis') && act === 'neardup') return topOfMindApi.fisNearDup({});
    if ((cat === 'nlp' || cat === 'filesystem' || cat === 'fis') && act === 'classify') return topOfMindApi.fisClassify({ file_path: args[0] || '' });
    if (comm && act === 'send') return topOfMindApi.mattermostSend({ channel: args[0] || 'codex', message: args.slice(1).join(' ') });
    if (comm && act === 'broadcast') return topOfMindApi.mattermostBroadcast({ message: args.join(' ') });
    throw new Error('Unknown /api command. Try /api filesystem intake <source_folder>, /api comm send codex "message", or /api nlp classify <file_path>.');
  }

  // Send message
  async function send() {
    if (!input.trim()) return;
    if (input.trim().toLowerCase().startsWith('/api ')) {
      const commandText = input.trim();
      setInput('');
      try {
        const result = await runApiSlashCommand(commandText);
        setNotice(`API command ran: ${result?.status || commandText}`);
      } catch (e) {
        setNotice(e.message);
      }
      return;
    }
    const payload = {
      source_id: srcId(selectedSource),
      source_label: srcName(selectedSource),
      body: input,
      role: 'user',
      wall: 'main',
      folder: selectedFolder.name || 'Main'
    };
    setInput('');
    try {
      const saved = await topOfMindApi.createMessage(payload);
      setMessages((m)=>[...m, saved]);
    } catch {
      setMessages((m)=>[...m, {...payload, id: `local-${Date.now()}`, created_at: new Date().toISOString()}]);
      setNotice('Draft shown locally; API post failed.');
    }
  }

  // Patch a message
  async function patchMessage(id, body) {
    setMessages(ms=>ms.map(m=>(m.id===id||m.message_id===id)?{...m,...body}:m));
    try { await topOfMindApi.updateMessage(id, body); } catch { setNotice('Local patch shown; API patch failed.'); }
  }

  // Create folder
  async function createFolder() {
    const name = prompt('Folder name?');
    if (!name) return;
    try { const f = await topOfMindApi.createFolder({ name, parent_id: selectedFolder.id || selectedFolder.folder_id }); setFolders(fs=>[...fs, f]); } catch { setNotice('Folder must be created by API; request failed.'); }
  }

  // Message counts by source
  const messageCounts = useMemo(() => {
    const bySource = {};
    messages.forEach((m) => {
      const s = m.source || m.source_id || m.source_label || 'unknown';
      bySource[s] = (bySource[s] || 0) + 1;
    });
    return { total: messages.length, bySource };
  }, [messages]);

  // Copy prompt to composer
  const copyPromptToComposer = useCallback((text) => {
    setInput((current) => (current ? current + '\n\n' + text : text));
  }, []);

  // Mic toggle
  const handleMicToggle = useCallback((enabled) => {
    setNotice(`Microphone ${enabled ? 'on' : 'off'}`);
  }, []);

  // Attach (placeholder)
  const handleAttach = useCallback(() => {
    setNotice('Attachments coming soon — needs upload endpoint.');
  }, []);

  // Derive active source name for composer placeholder
  const activeSourceName = srcName(selectedSource);

  return (
    <div className="app">
      {/* Left rail */}
      <nav className="rail global-rail" aria-label="Global navigation">
        <b>ToM</b>
        {globalNavItems.map((item) => (
          <button className={active===item.id?'on':''} onClick={()=>setActive(item.id)} key={item.id} title={item.label}>
            <span>{item.icon}</span><small>{item.label}</small>
          </button>
        ))}
      </nav>

      {/* Sidebar */}
      <Sidebar
        folders={folders}
        selectedFolder={selectedFolder}
        setSelectedFolder={setSelectedFolder}
        createFolder={createFolder}
        active={active}
        setActive={setActive}
      />

      {/* Funnel */}
      <Funnel
        sources={sources}
        setSources={setSources}
        selectedMessage={selectedMessage}
        patchMessage={patchMessage}
        collapsed={funnelCollapsed}
        setCollapsed={setFunnelCollapsed}
        activeAgentId={activeAgentId}
        setActiveAgentId={setActiveAgentId}
      />

      {/* Main content */}
      <main>
        <header>
          <h1>Top of Mind Desk</h1>
          <span className={`status ${online?'ok':'bad'}`}>
            {online?'● live':'○ offline'} · {topOfMindApi.baseUrl}
          </span>
        </header>

        <section className="workspace">
          {/* Chats view */}
          {active === 'chats' && (
            <div className="chats-layout conversation-layout">
              {/* Source filter rail */}
              <SourceFilter
                sources={sources}
                activeFilter={chatFilter}
                onFilterChange={setChatFilter}
                messageCounts={messageCounts}
                online={online}
              />

              {/* Chat area */}
              <div className="chats-main">
                <ChatView
                  messages={messages}
                  onPatchMessage={patchMessage}
                  onSelectMessage={setSelectedMessage}
                  filterSource={chatFilter}
                />

                {/* Footer composer */}
                <footer className="chat-footer">
                  <div className="cmd">
                    <button onClick={()=>topOfMindApi.combine({ folder_code: selectedFolder.folder_code })}>Combine</button>
                    <button>Split</button>
                    <button>Broadcast</button>
                    <button onClick={()=>topOfMindApi.endAll()}>End all</button>
                    <span>source_code {selectedSource.source_code}</span>
                    <span>folder_code {selectedFolder.folder_code}</span>
                  </div>
                  <Composer
                    input={input}
                    setInput={setInput}
                    onSend={send}
                    onMicToggle={handleMicToggle}
                    onAttach={handleAttach}
                    busy={false}
                    activeSource={activeSourceName}
                  />
                </footer>
              </div>
              <ConversationOSPanel sources={sources} messages={messages} onCopyToComposer={copyPromptToComposer} setNotice={setNotice} />
            </div>
          )}

          {/* Prompts view */}
          {active === 'prompts' && (
            <PromptsPanel onCopyToComposer={copyPromptToComposer} />
          )}

          {/* Other views (unchanged) */}
          {active === 'clipboard' && <ClipboardWorkspace onSendToComposer={copyPromptToComposer} setNotice={setNotice} />}
          {active === 'agents' && <ObjectRegistryPage kind="agents" onAction={setNotice} onCopyToComposer={copyPromptToComposer} />}
          {active === 'models' && <ObjectRegistryPage kind="models" onAction={setNotice} onCopyToComposer={copyPromptToComposer} />}
          {active === 'plugins' && <ObjectRegistryPage kind="plugins" onAction={setNotice} onCopyToComposer={copyPromptToComposer} />}
          {active === 'workflows' && <ObjectRegistryPage kind="workflows" onAction={setNotice} onCopyToComposer={copyPromptToComposer} />}
          {active === 'apis' && <ApiShelfPanel setNotice={setNotice} />}
          {active === 'memory' && <SearchPanel title="Memory search" modeToggle onSearch={(q,m)=>topOfMindApi.searchMemory(q,m==='vector'?'vector':undefined)} />}
          {active === 'files' && <SearchPanel title="File cache search" onSearch={(q)=>topOfMindApi.searchFileCache(q)} />}
          {active === 'settings' && <SettingsPanel online={online} setOnline={setOnline} setNotice={setNotice} />}
          {active === 'operator' && (
            <section className="panel">
              <h3>Operator drafts</h3>
              <textarea placeholder='{"action":"write_text","path":"notes.txt","text":"draft only"}'/>
              <textarea placeholder='{"action":"append_text","path":"notes.txt","text":"draft only"}'/>
              <button onClick={()=>setNotice('Draft only. Review before sending to /operator/file-actions or /operator/commands.')}>Do not run destructive action</button>
            </section>
          )}
        </section>
      </main>

      {/* Operator surface */}
      <OperatorSurface selectedSource={selectedSource} input={input} setNotice={setNotice} setSources={setSources} />

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} setActive={setActive} setInput={setInput} sources={sources} folders={folders} setNotice={setNotice} />

      {/* Notice toast */}
      {notice && (
        <div className="notice-toast" onClick={() => setNotice('')}>
          {notice}
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
