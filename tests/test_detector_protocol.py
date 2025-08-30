from typing import List

from redactor.detect.base import DetectionContext, Detector, EntityLabel, EntitySpan


class DummyDetector:
    def name(self) -> str:  # pragma: no cover - trivial
        return "dummy"

    def detect(self, text: str, context: DetectionContext | None = None) -> List[EntitySpan]:
        _ = context
        return [
            EntitySpan(0, len(text), text, EntityLabel.OTHER, "dummy", 1.0),
        ]


def test_dummy_detector_runtime_checkable() -> None:
    dummy = DummyDetector()
    assert isinstance(dummy, Detector)
    spans = dummy.detect("test")
    assert isinstance(spans, list)
    assert spans and isinstance(spans[0], EntitySpan)
