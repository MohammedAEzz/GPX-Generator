"""Coordinate parsing messages."""

import math

import pytest

from naveera_gpx.domain.coordinates import parse_point


def test_accepts_comma_separated_text():
    assert parse_point("39.69, -105.08") == (39.69, -105.08)


def test_accepts_lat_lon_pair():
    assert parse_point([39.69, -105.08]) == (39.69, -105.08)


def test_rejects_latitude_out_of_range():
    with pytest.raises(ValueError, match="between -90 and 90"):
        parse_point([91, 0])


def test_rejects_longitude_out_of_range():
    with pytest.raises(ValueError, match="between -180 and 180"):
        parse_point([0, 181])


def test_rejects_nan():
    with pytest.raises(ValueError, match="finite"):
        parse_point([math.nan, 0.0])


def test_rejects_infinity():
    with pytest.raises(ValueError, match="finite"):
        parse_point("inf, 0")


def test_rejects_non_numeric_text():
    with pytest.raises(ValueError, match="must be numbers"):
        parse_point("north, west")


def test_rejects_wrong_arity_text():
    with pytest.raises(ValueError, match="two numbers"):
        parse_point("1, 2, 3")


def test_rejects_wrong_arity_sequence():
    with pytest.raises(ValueError, match="two numbers"):
        parse_point([1])


def test_rejects_boolean_coordinates():
    with pytest.raises(ValueError, match="not true/false"):
        parse_point([True, 1.0])


def test_rejects_empty_text():
    with pytest.raises(ValueError, match="Enter latitude and longitude"):
        parse_point("  ")
