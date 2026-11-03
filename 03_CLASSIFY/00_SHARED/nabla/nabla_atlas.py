#!/usr/bin/env python3
"""Nabla Atlas deterministic core: address/hash validation and diagnostic scaffolding.
Semantic judgments must be supplied by a human or model and remain provenance-tagged.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from dataclasses import dataclass, asdict
from pathlib import Path

TIE = ["E", "C", "G", "K", "M", "T", "R", "F", "S", "Q"]
VARS = set(TIE)
DOMAINS = {"THEOPHYSICS","SCIENCE","LAW","MEDICINE","FINANCE","PERSONAL","TECH","EDUCATION","GOVERNANCE","ART","BUSINESS","RELIGION","HISTORY","UNKNOWN"}
AUDIENCES = {"SELF", "TEAM", "PUBLIC", "AI_RESEARCH"}
STATES = {"D","W","F","P","A","X"}; USES={"I","B","T","R"}; RISKS={"R0","R1","R2","R3","R4"}

def require(ok: bool, msg: str):
    if not ok: raise ValueError(msg)

def safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-") or "X"

def vector_string(v: dict[str,int]) -> str:
    validate_vector(v)
    return "".join(f"{x}{v[x]}" for x in ["G","M","E","S","T","K","R","Q","F","C"])

def validate_vector(v: dict[str,int]):
    require(set(v)==VARS, f"vector keys must be exactly {sorted(VARS)}")
    require(all(x in (0,3) for x in v.values()), "Nabla scores must be 0 or 3")

def ranking(v: dict[str,int]) -> list[str]:
    validate_vector(v)
    return sorted(TIE, key=lambda x: (-v[x], TIE.index(x)))

def semantic_hash(v: dict[str,int]) -> str:
    r=ranking(v)
    return "".join(f"[{r[i]}·{r[-1-i]}]" for i in range(5))

@dataclass
class Filing:
    domain: str; entity: str; state: str; audience: str; use: str; risk: str
    def validate(self):
        require(self.domain in DOMAINS, f"unknown domain {self.domain}")
        require(self.state in STATES, f"unknown state {self.state}")
        require(self.audience in AUDIENCES, f"unknown audience {self.audience}")
        require(self.use in USES, f"unknown use {self.use}")
        require(self.risk in RISKS, f"unknown risk {self.risk}")
    def address_prefix(self):
        self.validate(); return "/".join([self.domain,safe(self.entity),self.state,safe(self.audience),self.use,self.risk])

@dataclass
class NablaRecord:
    filing: Filing; vector: dict[str,int]; confidence: dict[str,float]; review_flags: list[str]
    def validate(self):
        self.filing.validate(); validate_vector(self.vector)
        require(set(self.confidence)==VARS, "confidence keys must match vector")
        require(all(0<=x<=1 for x in self.confidence.values()), "confidence must be 0..1")
    def address(self):
        self.validate(); return f"{self.filing.address_prefix()} :: {vector_string(self.vector)} :: {semantic_hash(self.vector)}"
    def filename_safe(self, stem="artifact"):
        return safe(f"{self.filing.domain}-{self.filing.entity}-{self.filing.state}-{self.filing.audience}-{self.filing.use}-{self.filing.risk}-{vector_string(self.vector)}")+"-"+safe(stem)
    def to_dict(self):
        self.validate(); return {"address":self.address(),"filename_safe":self.filename_safe(),"filing":asdict(self.filing),"vector":self.vector,"hash":semantic_hash(self.vector),"confidence_by_variable":self.confidence,"review_flags":self.review_flags}

def parse_input(obj: dict) -> NablaRecord:
    return NablaRecord(Filing(**obj["filing"]), obj["vector"], obj["confidence"], obj.get("review_flags",[]))

def decode(address: str) -> dict:
    p=[x.strip() for x in address.split("::")]; require(len(p)==3,"address must have prefix :: vector :: hash")
    vals=p[0].split("/"); require(len(vals)==6,"prefix must have D/N/V/A/U/R")
    pairs=re.findall(r"([GMESTKRQFC])([03])",p[1]); require(len(pairs)==10,"bad vector")
    v={k:int(x) for k,x in pairs}; validate_vector(v)
    expected=semantic_hash(v)
    return {"filing":{"domain":vals[0],"entity":vals[1],"state":vals[2],"audience":vals[3],"use":vals[4],"risk":vals[5]},"vector":v,"dominant":[x for x in ranking(v) if v[x]==3],"absent":[x for x in ranking(v) if v[x]==0],"hash_expected":expected,"hash_given":p[2],"hash_valid":expected==p[2]}

def chi_status(factors: dict[str,float]) -> dict:
    keys={"G","M_eff","E_signal","S_eff","T","K","R","Q","F","C"}
    require(set(factors)==keys,"chi factors must be G,M_eff,E_signal,S_eff,T,K,R,Q,F,C")
    require(all(0<=x<=1 for x in factors.values()),"chi factors must be 0..1")
    product=1.0
    for x in factors.values(): product*=x
    return {"chi_proxy":round(product,6),"qualitative":"ZERO/COLLAPSED" if min(factors.values())==0 else "HIGH" if product>=.5 else "MEDIUM" if product>=.1 else "LOW","warning":"This is a coherence profile, not a truth score or evidence substitute."}

def load(path: str): return json.loads(Path(path).read_text(encoding="utf-8"))
def dump(obj): print(json.dumps(obj,indent=2,ensure_ascii=False))
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    for n in ("address","validate"): x=sub.add_parser(n); x.add_argument("input")
    x=sub.add_parser("decode"); x.add_argument("address")
    x=sub.add_parser("chi"); x.add_argument("input")
    a=ap.parse_args()
    if a.cmd in ("address","validate"):
        r=parse_input(load(a.input)); dump(r.to_dict() if a.cmd=="address" else {"valid":True,"address":r.address()})
    elif a.cmd=="decode": dump(decode(a.address))
    else: dump(chi_status(load(a.input)))
if __name__=="__main__": main()
