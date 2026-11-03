'use strict';
(() => {
  let pending=false;
  const el=id=>document.getElementById(id);
  async function tick(){
    if(pending)return;
    pending=true;
    try{
      const response=await fetch('/api/progress');
      if(!response.ok)throw Error('Worker unavailable');
      const d=await response.json(), p=d.progress||{};
      window.fisLivePhase=p.phase;
      el('crawl-light').textContent='? '+(p.phase||d.status);
      if(typeof state!=='undefined'&&state?.config?.roots?.length)el('root-label').textContent=state.config.roots[0];
      const age=p.updated?Math.max(0,d.server_time-p.updated):null;
      const active=age!==null&&age<10&&!['complete','paused','waiting','folder error'].includes(p.phase);
      el('live-monitor').classList.toggle('is-active',active);
      el('live-phase').textContent=p.phase||'Waiting for worker';
      el('live-path').textContent=p.path||'No worker events yet';
      el('live-fresh').textContent=age===null?'No updates':`Worker updated ${Math.floor(age)}s ago`;
      const counts=[['Folders discovered',p.folders_discovered??(d.done+d.remaining)],['Files classified',d.files],['HTML folders completed',d.done],['Need template',d.waiting_templates],['Errors',d.errors]];
      el('live-counts').replaceChildren(...counts.map(([label,value])=>{const box=document.createElement('div'),number=document.createElement('b'),caption=document.createElement('span');number.textContent=Number(value||0).toLocaleString();caption.textContent=label;box.append(number,caption);return box;}));
      const events=(p.events||[]).slice(-12).reverse();
      el('live-events').replaceChildren(...events.map(event=>{const row=document.createElement('li'),time=document.createElement('time'),phase=document.createElement('strong'),path=document.createElement('span');time.textContent=new Date(event.at*1000).toLocaleTimeString();phase.textContent=event.phase;path.textContent=event.path;row.append(time,phase,path);return row;}));
      document.querySelectorAll('.live-track span').forEach((node,i)=>{const phases=['discover','read','fingerprint','classif','writing'];node.classList.toggle('current',String(p.phase).startsWith(phases[i]));});
    }catch(error){el('live-fresh').textContent='Disconnected â€” retrying';el('live-monitor').classList.remove('is-active');}
    finally{pending=false;}
  }
  tick();setInterval(tick,1800);
})();
