"use strict";
const initial=JSON.parse(document.getElementById('fis-folder-record').textContent);
const $=id=>document.getElementById(id), selected=new Set();
let files=initial.files, state=initial.state, busy=false;
const hub=initial.hub;
let folderView=initial.view;
function el(tag,text,cls){const n=document.createElement(tag);n.textContent=text??'';if(cls)n.className=cls;return n;}
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-FIS-Token':document.querySelector('meta[name=fis-session]').content}:{},body:body?JSON.stringify(body):undefined});const value=await r.json();if(!r.ok)throw Error(value.detail||'Request failed');return value;}
function notice(text,error=false){$('message').textContent=text;$('message').className=error?'error':'status';}
function renderState(){
  $('hub-nav').replaceChildren();$('overview').replaceChildren();
  for(const h of state.hubs){const a=el('a',h.label);a.href='folder?id='+encodeURIComponent(h.id);$('hub-nav').append(a);
    if(!hub){const card=el('section','', 'hub-card');const link=el('a',h.label);link.href=a.href;card.append(link,el('p',h.root,'source'),el('p',`${h.files} files · ${h.online?'online':'offline'} · ${h.enabled?'enabled':'paused'}`));$('overview').append(card);}}
  $('overview').className='hub-grid';$('relay-status').textContent=`${state.mana.queued} receipts ready for Mana · destination pending`;
  $('commands').replaceChildren();for(const c of state.commands.slice(0,8))$('commands').append(el('p',`${c.action} · ${c.status} · ${c.created}${c.error?' · '+c.error:''}`,'muted'));
  $('connection').textContent='Connected to local service';
  if(hub){const current=state.hubs.find(h=>h.id===hub.id),check=current?.last_check;$('folder-controls').hidden=false;
    $('pause').textContent=current?.enabled?'Pause hub':'Resume hub';
    $('checked').textContent=check?`Last checked ${new Date(check.checked).toLocaleString()} · ${check.stats.unchanged} unchanged · ${check.stats.errors} observation errors`:'Not scanned yet. Check for changes to establish a baseline.';
    $('changes').replaceChildren();if(check)for(const [kind,paths] of Object.entries(check.changes)){const d=el('details');d.append(el('summary',`${paths.length} ${kind}`));for(const p of paths)d.append(el('p',p,'source'));$('changes').append(d);}
    $('ai-status').textContent=state.ai.configured?'DeepSeek connected through the backend. Selected source excerpts may be partial.':'DeepSeek key is not configured in this server process. Folder checks and reading still work.';
    $('subfolders').replaceChildren();for(const child of folderView.children){const a=el('a',child.name);a.href='folder?id='+encodeURIComponent(hub.id)+'&relative='+encodeURIComponent(child.relative);const line=el('p');line.append(a);$('subfolders').append(line);}
  }else $('add-section').hidden=false;
}
function renderFiles(){const q=$('filter').value.toLowerCase();$('files').replaceChildren();
  for(const f of files){if(!(f.path+' '+f.preferred_title).toLowerCase().includes(q))continue;
    const row=el('div','', 'hub-row'+(f.present?'':' missing')),box=document.createElement('input');box.type='checkbox';box.checked=selected.has(f.path);box.disabled=!f.present;box.setAttribute('aria-label','Include '+f.preferred_title+' in question');
    box.onchange=()=>{if(box.checked&&selected.size>=3){box.checked=false;notice('Select at most three sources.',true);return;}box.checked?selected.add(f.path):selected.delete(f.path);};
    const desc=el('div');desc.append(el('strong',f.preferred_title||f.path),el('div',f.path,'source'),el('div',`${f.present?'present':'missing path'} · ${f.record_type} · Nabla ${f.nabla_address||f.nabla_status} · ${f.readable==='yes'?'text available':f.readable}`,'muted'));
    const read=el('button','Read');read.disabled=!f.present||f.readable!=='yes';read.onclick=()=>run('read',{relative:f.path});row.append(box,desc,read);$('files').append(row);}
}
async function refresh(){state=await api('api/state');if(hub){folderView=await api('api/view?hub='+encodeURIComponent(hub.id)+'&relative='+encodeURIComponent(folderView.relative));files=folderView.files;}renderState();if(hub)renderFiles();}
async function run(action,extra={}){if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);notice(action==='ask'?'Asking DeepSeek…':'Working…');
  try{const value=await api('api/commands',{action,hub:hub.id,...extra});if(value.status==='failed')throw Error(value.error);const result=value.result;
    if(action==='ask')$('answer').textContent=result.answer||result.message;
    if(action==='read'){$('source-title').textContent=result.path;$('source-note').textContent=`SHA-256 ${result.sha256} · ${result.partial?'EXCERPT: first 12,000 characters':'complete extracted text'}`;$('source-body').textContent=result.text;$('source-dialog').showModal();}
    notice('Done.');await refresh();
  }catch(e){notice(e.message,true);}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);if(hub)renderFiles();}}
$('check').onclick=()=>run('scan');$('refresh').onclick=()=>run('refresh');$('ask').onclick=()=>run('ask',{question:$('question').value,sources:[...selected],folder:folderView.relative});$('filter').oninput=renderFiles;$('close-source').onclick=()=>$('source-dialog').close();
$('pause').onclick=()=>run(state.hubs.find(h=>h.id===hub.id)?.enabled?'pause':'resume');
$('add-hub').onsubmit=async e=>{e.preventDefault();try{const data=Object.fromEntries(new FormData(e.target));await api('api/hubs',data);e.target.reset();await refresh();notice('Hub added.');}catch(error){notice(error.message,true);}};
renderState();if(hub)renderFiles();
if(location.protocol==='file:'){notice('Saved folder snapshot. Open http://127.0.0.1:28280/fis/ for live checks and chat.');$('connection').textContent='Offline snapshot';document.querySelectorAll('button').forEach(b=>b.disabled=true);}
else setInterval(()=>{if(!busy)refresh().catch(e=>{$('connection').textContent='Service unavailable';});},10000);
