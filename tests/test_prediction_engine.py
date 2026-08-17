import datetime as dt

from hub.intelligence.prediction_engine import PredictionEngine


def test_prediction_engine_learns_destination_and_permanent_rule(tmp_path):
    engine = PredictionEngine(tmp_path / "predictions")
    base = dt.datetime.now(dt.timezone.utc)

    for index in range(24):
        engine.observe(
            action="move",
            file_path=f"C:/Users/David/Downloads/invoice_{index:02d}.pdf",
            destination=f"D:/Finance/Invoices/2026/invoice_{index:02d}.pdf",
            timestamp=base - dt.timedelta(days=24 - index),
        )

    prediction = engine.predict(file_path="C:/Users/David/Downloads/invoice_new.pdf", action="move")

    assert prediction.destination
    assert prediction.destination.endswith("finance/invoices/2026")
    assert prediction.confidence > 0
    assert any(name == "destination_frequency" for name, _, _ in prediction.reasons)

    engine.correct(prediction.id, actual_destination="D:/Finance/Invoices/2026")
    rule = engine.make_permanent(prediction.id)

    assert rule == {"status": "rule_created", "pattern": "*.pdf"}
    assert engine.predict(file_path="C:/Users/David/Downloads/another.pdf", action="move").confidence == 1.0
    engine.close()


def test_prediction_engine_tracks_overrides_in_accuracy(tmp_path):
    engine = PredictionEngine(tmp_path / "predictions")
    for index in range(20):
        engine.observe(
            action="move",
            file_path=f"C:/Users/David/Downloads/photo_{index}.png",
            destination=f"D:/Pictures/Screenshots/photo_{index}.png",
        )

    prediction = engine.predict(file_path="C:/Users/David/Downloads/photo_new.png", action="move")
    engine.correct(prediction.id, actual_destination="D:/Pictures/Family")

    accuracy = engine.db.accuracy()
    assert accuracy["total_predictions"] == 1
    assert accuracy["correct"] == 0
    assert accuracy["accuracy"] == 0
    engine.close()
