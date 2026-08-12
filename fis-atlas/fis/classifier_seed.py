# fis-op: und
"""Classification seed lexicon — pulled from the X-drive NLP classifier.

Source: X:/04_STATIONS/paper-intelligence-suite.station/03_THEOPHYSICS_METRICS/
        theophysics_scorer.py  (WISDOM/KNOWLEDGE/COHERENCE terms, the 12 FRUITS +
        anti-fruits, the 10 ME_VARS). This is the "main classification stuff" —
        God and its forms categorized (divine/holy/logos/christ/grace…). Wiring it
        in makes the NLP classification ALWAYS part of the tagger run, not optional.
"""
from __future__ import annotations

WISDOM = ["wisdom", "discernment", "eternal", "transcend", "revelation", "mystery",
          "grace", "covenant", "truth", "logos", "spirit", "divine", "sacred", "holy",
          "virtue", "righteousness", "soul", "prayer", "faith", "love", "hope",
          "redemption", "atonement", "resurrection", "kingdom"]

KNOWLEDGE = ["data", "evidence", "experiment", "measure", "calculate", "equation",
             "formula", "theorem", "proof", "derive", "quantum", "physics", "entropy",
             "probability", "statistical", "empirical", "observation", "hypothesis",
             "analysis", "sigma", "decoherence", "wavefunction", "superposition",
             "photon", "spacetime", "information"]

FRUITS = {
    "love": ["love", "care", "sacrifice", "agape", "charity", "compassion", "communion", "covenantal"],
    "joy": ["joy", "delight", "gladness", "flourish", "rejoice", "abundance", "gratitude"],
    "peace": ["peace", "harmony", "reconcile", "rest", "shalom", "stability", "wholeness", "calm"],
    "patience": ["patience", "wait", "endure", "endurance", "persist", "perseverance", "longsuffering"],
    "kindness": ["kindness", "tender", "compassion", "mercy", "gentle", "generosity", "hospitality"],
    "goodness": ["goodness", "righteous", "righteousness", "integrity", "upright", "virtue", "justice", "honest"],
    "faithfulness": ["faithfulness", "faithful", "loyal", "reliable", "covenant", "steadfast", "fidelity", "promise"],
    "gentleness": ["gentleness", "meek", "humble", "humility", "lowly", "restraint"],
    "self_control": ["self-control", "discipline", "restraint", "temperance", "sober", "moderation", "mastery"],
    "grace": ["grace", "unmerited", "freely", "gift"],
    "hope": ["hope", "future", "promise", "expectation"],
    "humility": ["humble", "humility", "servant", "lowly"],
}

ME_VARS = {
    "G_gravity_belonging": ["gravity", "belonging", "community", "gather", "love", "binding", "together"],
    "M_mass_meaning": ["meaning", "purpose", "mass", "commit", "covenant", "hold"],
    "E_entropy_engagement": ["entropy", "energy", "work", "engage", "effort", "action", "decay"],
    "S_spacetime_structure": ["spacetime", "structure", "geometry", "context", "space", "time"],
    "T_time_eternity": ["time", "eternal", "sequence", "cause", "before", "after", "duration"],
    "K_knowledge_logos": ["knowledge", "logos", "word", "information", "encode", "transmit"],
    "R_relationship": ["relationship", "connect", "communicate", "interact", "bond", "between"],
    "Q_quantum_observer": ["quantum", "observer", "measurement", "collapse", "wavefunction", "consciousness"],
    "F_faith_coupling": ["faith", "coupling", "align", "trust", "belief", "voluntary"],
    "C_christ_coherence": ["christ", "coherence", "holds", "integration", "complete"],
}


def seed_lexicon() -> dict[str, list[str]]:
    """The full categorized classification lexicon as {category: [terms]}."""
    lex: dict[str, list[str]] = {"WISDOM": WISDOM, "KNOWLEDGE": KNOWLEDGE}
    for name, terms in FRUITS.items():
        lex[f"FRUIT_{name}"] = terms
    for name, terms in ME_VARS.items():
        lex[f"ME_{name}"] = terms
    return lex
