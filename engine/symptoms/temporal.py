from __future__ import annotations
import time
from collections import Counter
from datetime import datetime
from ._common import result,walk
from .models import Severity

def detect_time_bombs(folder_path):
    files,_=walk(folder_path); now=time.time()
    return [result("T01","Time bomb","Temporal",Severity.LOW,f,"Not accessed for over six months",age_days=int((now-f.stat().st_atime)/86400)) for f in files if now-f.stat().st_atime>183*86400]
def detect_burst_dump(folder_path):
    files,_=walk(folder_path); groups=Counter(datetime.fromtimestamp(f.stat().st_ctime).date().isoformat() for f in files)
    return [result("T02","Burst dump","Temporal",Severity.MEDIUM,__import__('pathlib').Path(folder_path).resolve(),f"{n} files share creation date {day}",date=day,count=n) for day,n in groups.items() if n>=50]
def detect_stale_pipeline(folder_path):
    _,dirs=walk(folder_path); now=time.time()
    return [result("T03","Stale pipeline","Temporal",Severity.MEDIUM,d,"Old pipeline artifact directory",age_days=int((now-d.stat().st_mtime)/86400)) for d in dirs if d.name.casefold() in {"output","outputs","temp","tmp","cache",".cache"} and now-d.stat().st_mtime>30*86400]
def detect_abandoned_workspace(folder_path):
    files,dirs=walk(folder_path); now=time.time(); base=__import__('pathlib').Path(folder_path).resolve(); out=[]
    for d in dirs:
        children=[f for f in files if d in f.parents]
        subdirs=[x for x in dirs if x.parent==d]
        if d!=base and subdirs and children and now-max(f.stat().st_mtime for f in children)>180*86400: out.append(result("T04","Abandoned workspace","Temporal",Severity.LOW,d,"Structured workspace has no recent changes"))
    return out
