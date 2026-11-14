"""Five-judge, read-only placement review for strict single-paper folders."""
from __future__ import annotations
import argparse, csv, json, re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

FUNCTION = ("type", "argument", "truth", "verification", "canon", "bridge_grade")
SEMANTIC = ("subjects", "laws", "slot_0001_scripture", "slot_0002_theology", "slot_0003_formal", "slot_0004_life")
STOP = {"the", "and", "of", "to", "for", "with", "paper", "final", "draft", "full", "copy"}

def folder(r): return str(PurePosixPath((r.get("file_path") or "").replace("\\", "/")).parent)
def base(r): return PurePosixPath((r.get("file_path") or "").replace("\\", "/")).name.casefold()
def toks(s): return {x for x in re.findall(r"[a-z0-9]+", (s or "").casefold()) if len(x)>2 and x not in STOP}
def vals(s): return {x.strip().casefold() for x in re.split(r"[;,/]", s or "") if x.strip()}
def best(scores):
    ranked=sorted(scores.items(), key=lambda x:(-x[1],x[0]))
    if not ranked or ranked[0][1]<=0: return None,0,0
    return ranked[0][0],ranked[0][1],ranked[0][1]-(ranked[1][1] if len(ranked)>1 else 0)

def vote(index: Path):
    with index.open("r",encoding="utf-8-sig",errors="replace",newline="") as f: rows=list(csv.DictReader(f,delimiter="\t"))
    groups=defaultdict(list); basename_count=Counter(base(r) for r in rows)
    for r in rows: groups[folder(r)].append(r)
    singles=[rs[0] for rs in groups.values() if len(rs)==1 and (rs[0].get("type") or "").casefold()=="paper" and basename_count[base(rs[0])]==1]
    profiles=defaultdict(list)
    for r in rows:
        if r not in singles and (r.get("series") or "").strip(): profiles[(r.get("series") or "").strip()].append(r)
    results=[]
    for p in singles:
        ballots={"registry":{"vote":(p.get("series") or "").strip(),"score":1.0,"evidence":"existing label; one vote only"}}
        pt=toks(PurePosixPath(p.get("file_path") or "").stem)
        scores={s:len(pt & set().union(*(toks(PurePosixPath(m.get("file_path") or "").stem) for m in ms[:500])))/max(1,len(pt)) for s,ms in profiles.items()}
        v,sc,mg=best(scores); ballots["identity"]={"vote":v,"score":round(sc,3),"margin":round(mg,3),"evidence":"title/code overlap"}
        scope=(p.get("road_or_scope") or "").strip().casefold(); parent=toks(folder(p)); scores={}
        for s,ms in profiles.items():
            same=sum(bool(scope) and (m.get("road_or_scope") or "").strip().casefold()==scope for m in ms)/len(ms)
            context=set().union(*(toks(folder(m)) for m in ms[:300])); scores[s]=same+0.25*len(parent&context)/max(1,len(parent))
        v,sc,mg=best(scores); ballots["structure"]={"vote":v,"score":round(sc,3),"margin":round(mg,3),"evidence":"scope/path neighborhood"}
        scores={}
        for s,ms in profiles.items():
            available=[f for f in FUNCTION if (p.get(f) or "").strip()]
            scores[s]=sum(any((m.get(f) or "").casefold()==(p.get(f) or "").casefold() for m in ms) for f in available)/max(1,len(available))
        v,sc,mg=best(scores); ballots["function"]={"vote":v,"score":round(sc,3),"margin":round(mg,3),"evidence":"argument/verification/canon function"}
        evidence=set().union(*(vals(p.get(f) or "") for f in SEMANTIC)); scores={}
        if evidence:
            for s,ms in profiles.items():
                corpus=set().union(*(vals(m.get(f) or "") for m in ms[:500] for f in SEMANTIC)); scores[s]=len(evidence&corpus)/max(1,len(evidence|corpus))
        v,sc,mg=best(scores); ballots["semantic"]={"vote":v,"score":round(sc,3),"margin":round(mg,3),"evidence":"subjects/laws/four slots" if v else "ABSTAIN: sparse fields"}
        counts=Counter(b["vote"] for b in ballots.values() if b["vote"]); ranked=counts.most_common(); winner,n=(ranked[0] if ranked else (None,0)); runner=ranked[1][1] if len(ranked)>1 else 0
        semantic=ballots["semantic"]["vote"]==winner
        status="ACCEPT" if n>=4 and semantic and n-runner>=2 else "REVIEW" if n>=3 and n-runner>=1 else "HOLD"
        results.append({"file_path":p.get("file_path"),"existing_series":p.get("series"),"proposed_series":winner,"votes":n,"runner_votes":runner,"status":status,"ballots":ballots})
    return {"schema":"david-os.singleton-group-vote.v1","source_mutations":False,"strict_single_papers":len(singles),"summary":dict(Counter(r["status"] for r in results)),"results":results}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--index",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args(); report=vote(a.index); a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"singleton_group_vote.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (a.output/"singleton_group_vote.csv").open("w",encoding="utf-8",newline="") as f:
        fields=["file_path","existing_series","proposed_series","votes","runner_votes","status","ballots"]; w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in report["results"]: w.writerow({**r,"ballots":json.dumps(r["ballots"],ensure_ascii=False)})
    print(json.dumps({"papers":report["strict_single_papers"],**report["summary"],"mutations":False}))
if __name__=="__main__": main()
