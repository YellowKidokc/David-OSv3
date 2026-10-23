from __future__ import annotations
import os,re,subprocess,time
from pathlib import Path
from ._common import result,walk
from .models import Severity

MARKERS={"package.json","requirements.txt","pyproject.toml","cargo.toml","go.mod",".git"}
def detect_program_root(folder_path):
    _,dirs=walk(folder_path); out=[]
    for d in dirs:
        found=sorted(x for x in MARKERS if (d/x).exists())
        if found: out.append(result("I01","Program-root danger","Infrastructure",Severity.CRITICAL,d,"Project root must never be moved automatically",markers=found))
    return out
def detect_toolchain_residue(folder_path):
    _,dirs=walk(folder_path); projects={d for d in dirs if any((d/x).exists() for x in MARKERS)}
    return [result("I02","Toolchain residue","Infrastructure",Severity.MEDIUM,d,"Build/cache artifact is outside a project",True) for d in dirs if d.name.casefold() in {"node_modules","__pycache__",".cache",".pytest_cache"} and not any(p==d or p in d.parents for p in projects)]
def detect_config_leak(folder_path):
    files,_=walk(folder_path); name_rx=re.compile(r"(?:^\.env(?:\.|$)|secret|credential|api[_-]?key|token)",re.I); content_rx=re.compile(rb"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}",re.I); out=[]
    for f in files:
        hit=bool(name_rx.search(f.name))
        if not hit and f.stat().st_size<1024*1024:
            try: hit=bool(content_rx.search(f.read_bytes()))
            except OSError: pass
        if hit: out.append(result("I03","Config leak","Infrastructure",Severity.CRITICAL,f,"Possible plaintext credential or secret"))
    return out
def detect_sync_ghost(folder_path):
    files,_=walk(folder_path); rx=re.compile(r"sync.?conflict|conflicted copy|conflict copy",re.I)
    return [result("I04","Sync ghost","Infrastructure",Severity.HIGH,f,"Cloud-sync conflict copy requires resolution") for f in files if rx.search(f.name)]
def detect_repo_mix(folder_path):
    _,dirs=walk(folder_path); out=[]
    for d in dirs:
        if not (d/".git").is_dir(): continue
        try: lines=subprocess.run(["git","-C",str(d),"status","--porcelain","--untracked-files=all"],capture_output=True,text=True,timeout=10,check=False).stdout.splitlines()
        except (OSError,subprocess.TimeoutExpired): continue
        loose=[x[3:] for x in lines if x.startswith("?? ")]
        if loose: out.append(result("I05","Repo / non-repo mix","Infrastructure",Severity.HIGH,d,f"{len(loose)} untracked files in repository",files=loose))
    return out
def detect_mirror_drift(folder_path):
    # A single root cannot establish a corresponding mirror safely.
    return []
def detect_broken_shortcuts(folder_path):
    files,_=walk(folder_path); out=[]
    for f in files:
        if f.suffix.lower()==".lnk" and os.name!="nt" and f.stat().st_size==0: out.append(result("I07","Shortcut graveyard","Infrastructure",Severity.LOW,f,"Empty shortcut cannot resolve",True))
    return out
def detect_log_accumulation(folder_path):
    files,_=walk(folder_path); now=time.time(); out=[]
    for f in files:
        if f.suffix.lower()==".log" and (f.stat().st_size>10*1024*1024 or now-f.stat().st_mtime>30*86400): out.append(result("I08","Log accumulation","Infrastructure",Severity.LOW,f,"Large or stale log needs rotation",True,size=f.stat().st_size))
    return out
