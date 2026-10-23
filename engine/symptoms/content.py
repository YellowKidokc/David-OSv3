from __future__ import annotations
import os,re
from collections import defaultdict
from pathlib import Path
from ._common import ARCHIVE_EXTS,DOC_EXTS,MEDIA_EXTS,TEXT_EXTS,digest,result,walk
from .models import Severity

def detect_duplicates(folder_path, *, files=None, stop=None, progress=None):
    """Exact duplicates; an existing inventory avoids another filesystem walk."""
    if files is None:
        files, _ = walk(folder_path)
    sizes = defaultdict(list)
    for f in files:
        if stop and stop():
            return []
        try:
            sizes[f.stat().st_size].append(f)
        except OSError:
            pass
    hashes = defaultdict(list)
    count = 0
    for group in sizes.values():
        if len(group) < 2:
            continue
        for f in group:
            if stop and stop():
                return []
            if (h := digest(f)):
                hashes[h].append(f)
            count += 1
            if progress and count % 100 == 0:
                progress(count, str(f.parent))
    return [result("C01", "Duplicate cluster", "Content", Severity.MEDIUM,
                   paths[0], f"{len(paths)} byte-identical files",
                   files=list(map(str, paths)), sha256=h)
            for h, paths in hashes.items() if len(paths) > 1]

def detect_format_redundancy(folder_path):
    files,_=walk(folder_path); groups=defaultdict(list)
    for f in files: groups[(f.parent,f.stem.casefold())].append(f)
    return [result("C02","Format redundancy","Content",Severity.LOW,p,f"'{s}' exists in {len({x.suffix.lower() for x in v})} formats",formats=sorted({x.suffix.lower() for x in v})) for (p,s),v in groups.items() if len({x.suffix.lower() for x in v})>1]

def detect_draft_graveyard(folder_path):
    files,_=walk(folder_path); cutoff=180*86400; now=__import__('time').time(); rx=re.compile(r"(?:draft|wip|old|temp|revision)",re.I)
    return [result("C03","Draft graveyard","Content",Severity.LOW,f,"Old draft-like file",age_days=int((now-f.stat().st_mtime)/86400)) for f in files if rx.search(f.stem) and now-f.stat().st_mtime>cutoff]

def detect_doc_chaos(folder_path):
    files,dirs=walk(folder_path); out=[]
    for d in dirs:
        local=[f for f in files if f.parent==d and f.suffix.lower() in DOC_EXTS]
        if len(local)>=5 and len({f.suffix.lower() for f in local})>=3: out.append(result("C04","Document chaos","Content",Severity.MEDIUM,d,"Many mixed document formats lack grouping",count=len(local)))
    return out

def detect_media_dump(folder_path):
    files,_=walk(folder_path); rx=re.compile(r"^(?:img[_-]?\d+|dsc[_-]?\d+|screenshot[_ -])",re.I)
    return [result("C05","Media dump","Content",Severity.LOW,f,"Media has an automatic name",True) for f in files if f.suffix.lower() in MEDIA_EXTS and rx.search(f.stem)]

def detect_unknown_blobs(folder_path):
    files,_=walk(folder_path); known=TEXT_EXTS|DOC_EXTS|MEDIA_EXTS|ARCHIVE_EXTS|{".exe",".msi",".dll",".db",".sqlite",".lnk",".chi",".fmeta",".srt",".toml",".ini",".cfg",".log"}
    return [result("C06","Unknown blob","Content",Severity.MEDIUM,f,"Unrecognized or absent extension") for f in files if f.suffix.lower() not in known]

def _encoding(f):
    try: data=f.read_bytes()[:65536]
    except OSError: return None
    if data.startswith((b'\xff\xfe',b'\xfe\xff')): return "utf-16"
    try: data.decode("utf-8"); return "utf-8"
    except UnicodeDecodeError: return "legacy/unknown"

def detect_encoding_chaos(folder_path):
    files,dirs=walk(folder_path); out=[]
    for d in dirs:
        enc=defaultdict(list)
        for f in files:
            if f.parent==d and f.suffix.lower() in TEXT_EXTS and (e:=_encoding(f)): enc[e].append(str(f))
        if len(enc)>1: out.append(result("C07","Encoding chaos","Content",Severity.MEDIUM,d,"Mixed text encodings",True,encodings=dict(enc)))
    return out

_THIN_MARKUP=re.compile(r"(?s)<(script|style)\b.*?</\1>|<[^>]+>|^---.*?^---|[#>*_`\[\]()|-]",re.M)

def content_weight(f,limit=262144):
    """Visible-character count for a text file: markup, front matter and bullets removed."""
    try:
        with f.open("rb") as stream:
            raw=stream.read(limit).decode("utf-8","ignore")
    except OSError: return None
    return len(_THIN_MARKUP.sub(" ",raw).split()) if raw is not None else None

def detect_thin_content(folder_path,min_words=25, *, files=None, stop=None):
    """C09 — empty or near-empty text files: nothing but a heading, a stub or whitespace."""
    if files is None:
        files,_=walk(folder_path)
    out=[]
    for f in files:
        if stop and stop(): return out
        if f.suffix.lower() not in TEXT_EXTS: continue
        try: size=f.stat().st_size
        except OSError: continue
        words=content_weight(f)
        if words is None: continue
        if size==0: out.append(result("C09","Thin content","Content",Severity.MEDIUM,f,"Empty file (0 bytes)",True,words=0,bytes=0))
        elif words<min_words: out.append(result("C09","Thin content","Content",Severity.LOW,f,f"Near-empty: {words} visible words",True,words=words,bytes=size))
    return out

def detect_incomplete_extract(folder_path):
    files,dirs=walk(folder_path); dirset={(d.parent,d.name.casefold()) for d in dirs}
    return [result("C08","Incomplete extraction","Content",Severity.LOW,f,"Archive and same-named extracted folder coexist") for f in files if f.suffix.lower() in ARCHIVE_EXTS and (f.parent,f.stem.casefold()) in dirset]
