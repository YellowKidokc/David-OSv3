from __future__ import annotations
import re,sqlite3
from collections import Counter
from pathlib import Path
from ._common import ARCHIVE_EXTS,DOC_EXTS,MEDIA_EXTS,TEXT_EXTS,result,walk
from .models import Severity

def detect_untagged_canonical(folder_path):
    files,_=walk(folder_path); out=[]
    for f in files:
        if "canonical" in {p.casefold() for p in f.parts} and f.suffix.lower() in TEXT_EXTS|DOC_EXTS and not Path(str(f)+".chi").exists() and not f.with_suffix(".chi").exists(): out.append(result("R01","Untagged canonical","Research Corpus",Severity.HIGH,f,"Canonical file has no .chi classification",True))
    return out
def detect_ai_debris(folder_path):
    files,_=walk(folder_path); rx=re.compile(r"(?:chatgpt|claude|gemini|conversation)[_-]?(?:export|session)?|(?:temp[_-]?)?prompt",re.I)
    return [result("R02","AI session debris","Research Corpus",Severity.MEDIUM,f,"Raw AI session or prompt artifact") for f in files if rx.search(f.stem)]
def detect_cross_purpose(folder_path):
    files,_=walk(folder_path); personal=re.compile(r"(?:family|vacation|invoice|receipt|bill|tax|medical)",re.I)
    return [result("R03","Cross-purpose pollution","Research Corpus",Severity.MEDIUM,f,"Personal-looking file is inside a research tree") for f in files if any("research" in p.casefold() or "papers" in p.casefold() for p in f.parts) and (personal.search(f.stem) or f.suffix.lower() in MEDIA_EXTS and personal.search(str(f.parent)))]
def detect_mixed_provenance(folder_path):
    files,dirs=walk(folder_path); marks={"openai":re.compile(r"chatgpt|openai|gpt[-_ ]?\d",re.I),"anthropic":re.compile(r"claude|anthropic",re.I),"google":re.compile(r"gemini|bard",re.I)}; out=[]
    for d in dirs:
        found={source for f in files if f.parent==d for source,rx in marks.items() if rx.search(f.name)}
        if len(found)>1: out.append(result("R04","Mixed provenance","Research Corpus",Severity.MEDIUM,d,"Outputs from multiple AI sources share a folder",sources=sorted(found)))
    return out
def detect_archive_pile(folder_path):
    files,_=walk(folder_path)
    return [result("R05","Archive pile","Research Corpus",Severity.LOW,f,"Archive is mixed with live working files") for f in files if f.suffix.lower() in ARCHIVE_EXTS and f.parent.name.casefold() not in {"archive","archives","backup","backups"} and any(x.parent==f.parent and x.suffix.lower() in TEXT_EXTS|DOC_EXTS for x in files)]
def _db_rows(root, query_options):
    db=next((p for n in ("chi_catalog_v2.db","chi_catalog.db") if (p:=root/n).is_file()),None)
    if not db:return []
    with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as con:
        for query in query_options:
            try:return con.execute(query).fetchall()
            except sqlite3.Error:continue
    return []
def detect_chi_gaps(folder_path):
    base=Path(folder_path).resolve(); rows=_db_rows(base,["SELECT path, chi_confidence FROM files WHERE chi_confidence < 0.3","SELECT file_path, confidence FROM files WHERE confidence < 0.3"])
    return [result("R06","Chi classification gap","Research Corpus",Severity.MEDIUM,Path(p),f"Classification confidence is {score}",confidence=score) for p,score in rows]
def detect_law_holes(folder_path):
    base=Path(folder_path).resolve(); rows=_db_rows(base,["SELECT law_primary, COUNT(*) FROM files WHERE law_primary IS NOT NULL GROUP BY law_primary"]); counts=dict(rows); expected=[f"L{i:02d}" for i in range(1,29)]
    return [result("R07","Law coverage hole","Research Corpus",Severity.HIGH,base,f"{law} has only {counts.get(law,0)} files",law=law,count=counts.get(law,0)) for law in expected if counts.get(law,0)<50] if rows else []
def detect_claim_gaps(folder_path):
    files,_=walk(folder_path); claim=re.compile(r"\b(?:therefore|proves?|demonstrates?|necessarily|we (?:argue|claim))\b",re.I); evidence=re.compile(r"(?:https?://|doi:|\[[0-9]+\]|\b(?:source|citation|evidence|according to)\b)",re.I); out=[]
    for f in files:
        if f.suffix.lower() not in TEXT_EXTS:continue
        try:text=f.read_text(encoding="utf-8",errors="replace")
        except OSError:continue
        claims=len(claim.findall(text)); citations=len(evidence.findall(text))
        if claims>=3 and citations/max(claims,1)<.3:out.append(result("R08","Claim without evidence","Research Corpus",Severity.HIGH,f,f"{claims} claim markers but only {citations} evidence markers",claims=claims,evidence=citations))
    return out
