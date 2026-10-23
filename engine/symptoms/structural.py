from __future__ import annotations
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from ._common import digest, result, walk
from .models import Severity, SymptomResult

def detect_ext_swamp(folder_path) -> list[SymptomResult]:
    files, dirs = walk(folder_path); out=[]
    for d in dirs:
        exts={f.suffix.lower() or "<none>" for f in files if f.parent == d}
        if len(exts)>8: out.append(result("S01","Extension swamp","Structural",Severity.MEDIUM,d,f"{len(exts)} file types share this folder",extensions=sorted(exts)))
    return out

def detect_version_sprawl(folder_path):
    files,_=walk(folder_path); groups=defaultdict(list)
    rx=re.compile(r"(?:[_ .-](?:v\d+(?:\.\d+)*|final(?:[_ -]final)*|copy)|\s*\(\d+\))$",re.I)
    for f in files:
        base=rx.sub("",f.stem).casefold()
        if base != f.stem.casefold(): groups[(f.parent,base)].append(f)
    return [result("S02","Version sprawl","Structural",Severity.MEDIUM,p,f"{len(v)} versions of {n}",files=[str(x) for x in v]) for (p,n),v in groups.items() if len(v)>1]

def detect_depth_explosion(folder_path):
    files,dirs=walk(folder_path); base=Path(folder_path).resolve(); out=[]
    for d in dirs:
        direct=[f for f in files if f.parent==d]
        if len(d.relative_to(base).parts)>5 and len(direct)<3 and not any(x.parent==d for x in dirs if x!=d): out.append(result("S03","Depth explosion","Structural",Severity.LOW,d,"Deep leaf folder contains fewer than 3 files",True,depth=len(d.relative_to(base).parts)))
    return out

def detect_flat_overload(folder_path):
    files,dirs=walk(folder_path)
    return [result("S04","Flat overload","Structural",Severity.MEDIUM,d,f"{len(v)} files with no organization") for d in dirs if len(v:=[f for f in files if f.parent==d])>200]

def detect_orphan_sidecar(folder_path):
    files,_=walk(folder_path); existing=set(files); out=[]
    for f in files:
        if f.suffix.lower() in {".fmeta",".chi",".srt"}:
            parent=Path(str(f)[:-len(f.suffix)])
            if parent not in existing: out.append(result("S05","Orphan sidecar","Structural",Severity.LOW,f,"Sidecar has no parent file",True,expected_parent=str(parent)))
    return out

def detect_naming_collision(folder_path):
    files,_=walk(folder_path); out=[]
    for parent in {f.parent for f in files}:
        local=[f for f in files if f.parent==parent]
        for i,a in enumerate(local):
            for b in local[i+1:]:
                if (a.name.casefold()==b.name.casefold() or SequenceMatcher(None,a.stem.casefold(),b.stem.casefold()).ratio()>=.92) and digest(a)!=digest(b):
                    out.append(result("S06","Naming collision","Structural",Severity.HIGH,parent,"Near-identical names have different content",files=[str(a),str(b)]))
    return out

def detect_project_scatter(folder_path):
    files,_=walk(folder_path); groups=defaultdict(set)
    for f in files:
        for token in set(re.findall(r"[a-z0-9]{5,}",f.stem.casefold())): groups[token].add(f.parent)
    return [result("S07","Project scatter","Structural",Severity.HIGH,Path(folder_path).resolve(),f"Keyword '{k}' appears across {len(v)} folders",folders=sorted(map(str,v))) for k,v in groups.items() if len(v)>=3]

def detect_phantom_refs(folder_path):
    files,_=walk(folder_path); out=[]; link=re.compile(r"\[[^]]*\]\(([^)#?]+)|\[\[([^]|#]+)")
    for f in files:
        if f.suffix.lower() not in {".md",".html",".htm"}: continue
        try: text=f.read_text(encoding="utf-8",errors="replace")
        except OSError: continue
        for m in link.finditer(text):
            target=(m.group(1) or m.group(2)).strip(); candidate=(f.parent/target)
            options=[candidate,candidate.with_suffix(".md")] if not candidate.suffix else [candidate]
            if not any(x.exists() for x in options) and "://" not in target: out.append(result("S08","Phantom reference","Structural",Severity.MEDIUM,f,f"Missing link target: {target}",target=target))
    return out
