from redactor.detect.base import EntityLabel
from redactor.detect.date_dob import DOBDetector


def test_dash_variants_single_date_binding() -> None:
    det = DOBDetector()
    text = "D.O.B.—  03/18/1976. Executed on 07/05/1982."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "03/18/1976"
    assert span.label is EntityLabel.DOB


def test_month_name_form() -> None:
    det = DOBDetector()
    text = "Date of Birth: May 9, 1960"
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].text == "May 9, 1960"


def test_stop_at_period() -> None:
    det = DOBDetector()
    text = "DOB: 08/05/1992. Signed 08/06/1992"
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].text == "08/05/1992"
