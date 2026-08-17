def sample_scan():
    return {
        "files": [
            {"path": "/GTQ/a.md", "domain": "theology", "reading_level": "college"},
            {"path": "/GTQ/b.md", "domain": "physics", "reading_level": "academic"},
            {"path": "/GTQ/c.html", "domain": "physics", "reading_level": "easy"},
        ],
        "exact_duplicates": [{"files": ["/a", "/b", "/c", "/d", "/e"]}],
        "near_duplicates": [{"file_a": "/GTQ/a.md", "file_b": "/GTQ/a-copy.md", "jaccard": 0.94}],
        "routing_suggestions": [
            {"path": "/GTQ/a.md", "target_folder": "theology"},
            {"path": "/GTQ/orphan.md", "target_folder": None},
        ],
        "rename_proposals": [
            {"current_name": "drv-02-the-lcok.html", "proposed_name": "drv-02-the-lock.html", "spelling_correction": True},
            {"current_name": "rough draft.md", "proposed_name": "TH__DOC__rough-draft__00000000__AC.md"},
        ],
        "classifications": [
            {"path": "/GTQ/a.md", "domain": "theology", "reading_level": "college", "domain_scores": {"physics": 0.51, "theology": 0.49}},
            {"path": "/GTQ/b.md", "domain": "physics", "reading_level": "academic"},
        ],
    }


def test_build_report_anomalies_first_and_feedback_shapes():
    from hub.services.report_builder import build_report

    report = build_report(sample_scan(), source="/GTQ", duration=2.5)

    assert report["text"].splitlines()[4] == "== ANOMALIES =="
    assert report["sections"]["anomalies"][0]["kind"] == "exact_duplicate"
    assert report["sections"]["statistics"]["duplicate_coverage_pct"] == 100.0
    spelling = report["sections"]["suggestions"][0]
    assert spelling["kind"] == "spelling_correction"
    assert spelling["badge"] == "RED"
    assert spelling["feedback"] == {"accept": True, "reject": True, "rate_1_to_5": True}
    assert report["sections"]["actions_taken"] == []


def test_fis_report_routes_create_ask_and_feedback():
    from hub.api.routes_fis import AskRequest, FeedbackRequest, ReportRequest, ask_fis_report, create_fis_report, feedback

    report = create_fis_report(ReportRequest(scan=sample_scan(), source="/GTQ", duration="2.5s"))

    asked = ask_fis_report(AskRequest(report_id=report["report_id"], question="how many exact dups?"))
    assert "exact duplicate groups" in asked["answer"]

    suggestion_id = report["sections"]["suggestions"][0]["id"]
    recorded = feedback(FeedbackRequest(report_id=report["report_id"], suggestion_id=suggestion_id, rating=5))
    assert recorded["feedback"]["accepted"] is True
