"""Master Equation naming, shared by FIS and presentation clients.

Pure functions only: no registry issuance, approvals, network or source writes.
Keyword substring matching, keyword order (including repeated entries), Python
rounding and local-time address dates intentionally preserve the legacy behavior.
Empty vectors return an empty name; presentation callers display UNSCORED.
"""
import json
import re
from datetime import datetime

SLOTS = tuple("GMESTKRQFC")
UNSCORED = "UNSCORED"

CHI_SIGNALS = {
    "G": {
        "name": "Grace",
        "law": "L01/L08",
        "keywords": [
            "grace","charis","gravitational","curvature","spacetime","geodesic",
            "gift","unmerited","favor","negentropic","provision","sovereign",
            "sustain","external source","persistent source","common grace",
            "gravity","einstein","tensor","manifold","frame independent",
        ]
    },
    "M": {
        "name": "Moral Alignment",
        "law": "L02",
        "keywords": [
            "moral","alignment","will","repentance","conversion","momentum",
            "inertia","obedience","surrender","submission","sanctification",
            "moral mass","m_eff","effective mass","force","acceleration",
            "resistance","sin nature","flesh","free will",
        ]
    },
    "E": {
        "name": "Truth Signal",
        "law": "L03",
        "keywords": [
            "truth","deception","witness","testimony","light","electromagnetic",
            "maxwell","glory","doxa","revelation","signal","noise","logos",
            "scripture","evidence","data","empirical","statistical","measure",
            "falsify","testable","hypothesis","verify","prediction","result",
        ]
    },
    "S": {
        "name": "Entropy",
        "law": "L05",
        "keywords": [
            "entropy","thermodynamic","second law","heat death","disorder",
            "chaos","judgment","justice","free energy","boltzmann","decay",
            "adversary","corruption","decoherence","dissipation","equilibrium",
            "irreversible","arrow of time","loss","noise","drift","attenuation",
        ]
    },
    "T": {
        "name": "Time / Kairos",
        "law": "L08",
        "keywords": [
            "time","kairos","chronos","temporal","duration","epoch","timeline",
            "history","sequence","order","moment","period","future","past",
            "relativity","lorentz","proper time","dilation","symmetry",
        ]
    },
    "K": {
        "name": "Knowledge",
        "law": "L06",
        "keywords": [
            "knowledge","information","shannon","logos","word","channel","capacity",
            "bandwidth","sanctification","logos","data","encoding","fidelity",
            "compression","transmission","noise","signal-to-noise",
            "epistemology","axiom","foundation","ground","method",
        ]
    },
    "R": {
        "name": "Relational Frame",
        "law": "L08",
        "keywords": [
            "relation","frame","reference","covenant","community","fellowship",
            "bond","connection","love","agape","relationship","binding",
            "lorentz","invariant","frame lock","mutual","partnership",
        ]
    },
    "Q": {
        "name": "Quantum / Uncertainty",
        "law": "L07",
        "keywords": [
            "quantum","collapse","superposition","measurement","faith","observer",
            "uncertainty","doubt","probability","wave function","planck",
            "hilbert","entanglement","coherence","decoherence","interference",
        ]
    },
    "F": {
        "name": "Faith / Fruit",
        "law": "L04/L07",
        "keywords": [
            "faith","trust","belief","hope","fruit","love","joy","peace",
            "patience","kindness","goodness","faithfulness","gentleness",
            "self-control","strong force","quark","binding","covenant",
            "confinement","agape","yukawa",
        ]
    },
    "C": {
        "name": "Christ Alignment / Coherence",
        "law": "L10",
        "keywords": [
            "christ","coherence","integration","shalom","kingdom","master equation",
            "decoherence","alignment","logos","salvation","cross","resurrection",
            "trinity","atonement","redemption","reconciliation","mediator",
            "coherent","integrated","unified","complete","perfect",
        ]
    },
}


def score_chi_factor(text: str, factor_key: str) -> int:
    """Return 0-3 score for one CHI factor based on keyword hits in text."""
    keywords = CHI_SIGNALS[factor_key]["keywords"]
    low      = text.lower()
    hits     = sum(1 for kw in keywords if kw in low)
    if hits == 0:   return 0
    if hits <= 2:   return 1
    if hits <= 5:   return 2
    return 3


COUPLING_PAIRS = [
    ("G", "C"),  # Grace ↔ Christ/Coherence (L01 ↔ L10)
    ("M", "F"),  # Moral Alignment ↔ Faith/Fruit (L02 ↔ L04)
    ("E", "Q"),  # Truth Signal ↔ Quantum/Uncertainty (L03 ↔ L07)
    ("S", "R"),  # Entropy ↔ Relational Frame (L05 ↔ L08)
    ("T", "K"),  # Time/Kairos ↔ Knowledge/Logos (L08 ↔ L06)
]


def meq_namer_string(chi: dict) -> str:
    """Build the Master Equation Namer identity string from a CHI vector.

    Format: G3 M2 E3 S1 T2 K3 R1 Q2 F3 C3 :: [G.C] [M.F] [E.Q] [S.R] [T.K]
    """
    if not chi or not any(chi.values()):
        return ""
    vector = " ".join(f"{var}{chi.get(var, 0)}" for var in "G M E S T K R Q F C".split())
    pairs = " ".join(f"[{a}.{b}]" for a, b in COUPLING_PAIRS)
    return f"{vector} :: {pairs}"


def meq_namer_short(chi: dict) -> str:
    """Shortened MEQ name: only non-zero variables + active coupling pairs."""
    if not chi or not any(chi.values()):
        return ""
    nonzero = [f"{var}{chi[var]}" for var in "G M E S T K R Q F C".split() if chi.get(var, 0) > 0]
    active_pairs = []
    for a, b in COUPLING_PAIRS:
        if chi.get(a, 0) > 0 or chi.get(b, 0) > 0:
            active_pairs.append(f"[{a}.{b}]")
    return " ".join(nonzero) + (" :: " + " ".join(active_pairs) if active_pairs else "")


def folder_meq_aggregate(files: list) -> str:
    """Compute aggregate MEQ vector for the folder from all file CHI vectors."""
    totals = {var: 0 for var in "G M E S T K R Q F C".split()}
    count = 0
    for row in files:
        local = json.loads(row["local_classification_json"] or "{}")
        chi = local.get("chi", {})
        if chi and any(chi.values()):
            for var in totals:
                totals[var] += int(chi.get(var, 0))
            count += 1
    if count == 0:
        return ""
    avg = {var: min(3, round(totals[var] / count)) for var in totals}
    return meq_namer_string(avg)


MEQ_KEYWORDS = re.compile(
    r"\b(master[\s_-]*equation|nabla|meq|master[\s_-]*eq|chi[\s_-]*field|lagrangian|coherence[\s_-]*equation)\b",
    re.IGNORECASE,
)


def lossless_slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w]+", "_", text).strip("_")
    return (slug or "folder")[:max_len].rstrip("_")


def propose_lossless_address(title: str, sample: str, source_mtime: float) -> dict:
    """Return a stable LOSS__/MEQ__ address without writing or moving content."""
    match = MEQ_KEYWORDS.search(f"{title}\n{sample}")
    mode = "meq" if match else "loss"
    prefix = "MEQ" if mode == "meq" else "LOSS"
    date_code = datetime.fromtimestamp(source_mtime).strftime("%Y-%m-%d")
    return {
        "address": f"{prefix}__{lossless_slug(title)}__{date_code}",
        "mode": mode,
        "source_date": date_code,
        "basis": "title_and_local_content_sample",
        "trigger": match.group(0) if match else None,
    }

