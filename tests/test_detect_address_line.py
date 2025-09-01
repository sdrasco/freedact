from __future__ import annotations

from typing import cast

import pytest

from redactor.detect.address_libpostal import AddressLineDetector
from redactor.detect.base import EntityLabel, EntitySpan


@pytest.fixture
def det() -> AddressLineDetector:
    return AddressLineDetector()


def _assert_span_basic(span: EntitySpan) -> None:
    assert span.label is EntityLabel.ADDRESS_BLOCK
    backend = cast(str, span.attrs["backend"])
    assert backend == "usaddress"


def test_street_basic(det: AddressLineDetector) -> None:
    text = "366 Broadway"
    spans = det.detect(text)
    assert len(spans) == 1
    span = spans[0]
    _assert_span_basic(span)
    assert span.text == "366 Broadway"
    assert cast(str, span.attrs["line_kind"]) == "street"
    comps = cast(dict[str, str], span.attrs["components"])
    assert comps["AddressNumber"] == "366"
    assert comps["StreetName"] == "Broadway"
    assert span.start == 0
    assert span.end == len("366 Broadway")


def test_street_normalized(det: AddressLineDetector) -> None:
    text = "1600 Pennsylvania Ave NW"
    span = det.detect(text)[0]
    assert cast(str, span.attrs["line_kind"]) == "street"
    assert cast(str, span.attrs["normalized"]).split() == [
        "1600",
        "Pennsylvania",
        "Ave",
        "NW",
    ]


@pytest.mark.parametrize("text", ["P.O. Box 123", "PO Box 123"])
def test_po_box(det: AddressLineDetector, text: str) -> None:
    span = det.detect(text)[0]
    _assert_span_basic(span)
    assert cast(str, span.attrs["line_kind"]) == "po_box"
    comps = cast(dict[str, str], span.attrs["components"])
    assert "USPSBoxType" in comps and "USPSBoxID" in comps
    assert cast(str, span.attrs["normalized"]).upper() == "PO BOX 123"


def test_city_state_zip(det: AddressLineDetector) -> None:
    text = "San Francisco, CA 94105"
    span = det.detect(text)[0]
    _assert_span_basic(span)
    assert cast(str, span.attrs["line_kind"]) == "city_state_zip"
    comps = cast(dict[str, str], span.attrs["components"])
    assert comps.get("PlaceName") == "San Francisco"
    assert comps.get("StateName") == "CA"
    assert comps.get("ZipCode") == "94105"
    start = text.index("San")
    end = start + len("San Francisco, CA 94105")
    assert span.start == start
    assert span.end == end


@pytest.mark.parametrize("text", ["Suite 210", "Apt 5B"])
def test_units(det: AddressLineDetector, text: str) -> None:
    span = det.detect(text)[0]
    assert cast(str, span.attrs["line_kind"]) == "unit"


def test_prefix_and_punctuation(det: AddressLineDetector) -> None:
    text1 = "Address: 123 Main St"
    span1 = det.detect(text1)[0]
    assert span1.text == "123 Main St"
    assert cast(bool, span1.attrs["trimmed_prefix"]) is True
    assert span1.start == text1.index("123")
    assert span1.end == span1.start + len("123 Main St")

    text2 = "(366 Broadway),"
    span2 = det.detect(text2)[0]
    assert span2.text == "366 Broadway"
    assert cast(str, span2.attrs["line_kind"]) == "street"


def test_multiple_lines_order(det: AddressLineDetector) -> None:
    text = "366 Broadway\nSan Francisco, CA 94105"
    spans = det.detect(text)
    assert [s.text for s in spans] == [
        "366 Broadway",
        "San Francisco, CA 94105",
    ]
    kinds = [cast(str, s.attrs["line_kind"]) for s in spans]
    assert kinds == ["street", "city_state_zip"]


@pytest.mark.parametrize(
    "text",
    [
        "Please provide your bank account number.",
        "Bank of Example, N.A.",
    ],
)
def test_negatives(det: AddressLineDetector, text: str) -> None:
    assert det.detect(text) == []


def test_unit_keyword_without_digits(det: AddressLineDetector) -> None:
    text = "Suite A"
    span = det.detect(text)[0]
    assert cast(str, span.attrs["line_kind"]) == "unit"
    comps = cast(dict[str, str], span.attrs["components"])
    assert comps.get("OccupancyType") == "Suite"
    assert comps.get("OccupancyIdentifier") == "A"


def test_po_box_prefilter(det: AddressLineDetector) -> None:
    text = "PO Box 123"
    span = det.detect(text)[0]
    assert cast(str, span.attrs["line_kind"]) == "po_box"


@pytest.mark.parametrize("text", ["Bank of Example, N.A.", "Main Street"])
def test_prefilter_non_addresses(det: AddressLineDetector, text: str) -> None:
    assert det.detect(text) == []
