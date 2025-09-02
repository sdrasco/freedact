from redactor.detect.base import EntityLabel
from redactor.detect.date_dob import DOBDetector


def test_dash_variants_single_date_binding() -> None:
    det = DOBDetector()
    text = "D.O.B.—  12/21/1975. Executed on 07/05/1982."
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.text == "12/21/1975"
    assert span.label is EntityLabel.DOB


def test_month_name_form() -> None:
    det = DOBDetector()
    text = "Date of Birth: July 4, 1982"
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].text == "July 4, 1982"


def test_stop_at_period() -> None:
    det = DOBDetector()
    text = "DOB: 07/04/1982. Signed 07/05/1982"
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].text == "07/04/1982"
