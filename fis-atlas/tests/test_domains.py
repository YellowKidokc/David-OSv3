from fis import domains


def test_named_domains_classify():
    packs = domains.load_packs()
    assert "theophysics" in packs and "day_trading" in packs and "obsidian" in packs
    assert domains.best_domain("The master equation governs the chi field and coherence")[0] == "theophysics"
    assert domains.best_domain("RSI and MACD show a bullish breakout above resistance")[0] == "day_trading"
    assert domains.best_domain("Use a dataview query over the vault frontmatter and backlinks")[0] == "obsidian"


def test_unknown_domain_escalates_and_proposes_vernacular():
    # a domain the tagger has no pack for -> unknown -> propose candidate vocabulary
    text = ("Sourdough hydration and autolyse determine crumb structure; the levain "
            "and banneton proof time change the oven spring of artisan bread.")
    result = domains.classify_or_escalate(text)
    assert result["status"] == "unknown"
    esc = result["escalation"]
    assert esc["tier"] == "inferred"                       # fetched vocab is never trusted as fact
    terms = esc["proposed_terms"]
    assert any(t in terms for t in ("sourdough", "levain", "banneton", "autolyse"))


def test_proposal_saved_as_inactive_needs_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(domains, "PACKS_DIR", tmp_path)
    prop = domains.PackProposal(proposed_terms=["levain", "banneton"], source="salient_terms")
    path = domains.save_proposal("baking", prop)
    body = path.read_text(encoding="utf-8")
    assert "status: proposed" in body and "needs approval" in body


def test_known_domain_not_flagged_unknown():
    r = domains.classify_or_escalate("candlestick volume ema fibonacci swing pre-market ticker")
    assert r["status"] == "known" and r["domain"] == "day_trading"
