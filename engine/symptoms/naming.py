from __future__ import annotations
import re
from ._common import ARCHIVE_EXTS,DOC_EXTS,result,walk
from .models import Severity
def detect_name_rot(folder_path):
    files,_=walk(folder_path); rx=re.compile(r"^(?:screenshot|img[_-]?\d|dsc[_-]?\d|untitled|new document)(?:[_ (.-]|$)",re.I)
    return [result("N01","Name rot","Naming",Severity.LOW,f,"Automatic name carries little meaning") for f in files if rx.search(f.stem)]
def detect_download_purgatory(folder_path):
    files,dirs=walk(folder_path); out=[]
    for d in dirs:
        local=[f for f in files if f.parent==d]; installers=[f for f in local if f.suffix.lower() in {".exe",".msi",".dmg"}|ARCHIVE_EXTS]
        if installers and any(f.suffix.lower() in DOC_EXTS for f in local): out.append(result("N02","Download purgatory","Naming",Severity.MEDIUM,d,"Installers/archives are mixed with documents",files=list(map(str,installers))))
    return out
def detect_tiny_debris(folder_path):
    files,dirs=walk(folder_path); return [result("N03","Tiny-folder debris","Naming",Severity.LOW,d,"Empty or hidden-only folder",True) for d in dirs if d.name and not [f for f in files if f.parent==d and not f.name.startswith('.') ] and not [x for x in dirs if x.parent==d]]
def detect_path_length(folder_path):
    files,dirs=walk(folder_path); return [result("N04","Path length danger","Naming",Severity.MEDIUM,p,f"Path is {len(str(p))} characters",length=len(str(p))) for p in files+dirs if len(str(p))>200]
