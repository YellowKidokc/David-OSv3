"""Run: python -m pytest tests/test_fingerprint.py -q   (or: python tests/test_fingerprint.py)
Measured cases from 2026-10-17. The v1 tests DOCUMENT known faults (they pass when the fault is present)."""
import itertools, random, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try: from engine import fingerprint as f
except ImportError: import fingerprint as f

random.seed(1)
A = ("Grace is the external source term that restores coherence when a closed system cannot repair itself. The Federal Reserve "
     "expanded the money supply after the war and the purchasing power of the dollar declined across the following decades. "
     "Families fragmented as trust in institutions fell and the semantic content of shared words drifted further from their "
     "original meaning. Every repair needs a source outside the damaged system, and every record of the damage is kept. ") * 4
EDIT = A.replace("declined", "collapsed", 1)
SHUF = " ".join(random.sample(A.split(), len(A.split())))
OTHER = ("The central bank raised interest rates to fight inflation, and markets reacted with volatility. Monetary policy "
         "shapes credit, employment and asset prices; the dollar's value depends on confidence in the institution and in "
         "the government that stands behind it. Critics argue the institution lacks accountability and transparency. ") * 4

def test_v1_known_faults():
    assert f.hamming(f.simhash(A), f.simhash(SHUF)) == 0          # blind to word order
    assert f.hamming(f.simhash(""), f.simhash("  ")) == 0          # empty files "match"

def test_exact():            assert f.near_dup(A, A)["verdict"] == "EXACT"
def test_light_edit():       assert f.near_dup(A, EDIT)["verdict"] in ("NEAR_DUPLICATE", "RELATED_VERSION")
def test_shuffled_differs(): assert f.near_dup(A, SHUF)["verdict"] == "DIFFERENT"
def test_other_paper():      assert f.near_dup(A, OTHER)["verdict"] == "DIFFERENT"
def test_too_short():        assert f.near_dup("Draft notes.", "Todo list.")["verdict"] == "TOO_SHORT"
def test_empty_never_matches(): assert f.simhash_v2("") is None

def test_no_false_matches_shared_vocab():
    words = (A + OTHER).lower().split()
    docs = [" ".join(random.choices(words, k=300)) for _ in range(60)]
    wrong = [p for p in itertools.combinations(docs, 2) if f.near_dup(*p)["verdict"] in ("NEAR_DUPLICATE",)]
    assert not wrong

if __name__ == "__main__":
    for n, fn in list(globals().items()):
        if n.startswith("test_"): fn(); print("PASS", n)
