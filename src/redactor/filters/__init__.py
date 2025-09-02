"""Utility filters for post-detection span processing."""

from .guards import filter_spans_for_safety, find_heading_ranges

__all__ = ["find_heading_ranges", "filter_spans_for_safety"]
