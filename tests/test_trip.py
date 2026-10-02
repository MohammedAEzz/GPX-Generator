"""Stop merging and trip JSON."""

import pytest

from naveera_gpx.domain.trip import (
    Step,
    merge_consecutive,
    trip_from_dict,
    trip_from_normal_fields,
    trip_from_pooled_fields,
    trip_to_dict,
)
from tests.fakes import DROPOFF, OTHER, PICKUP, START


def test_normal_trip_has_pickup_then_dropoff():
    trip = trip_from_normal_fields(
        name="Passenger A",
        start=START,
        pickup=PICKUP,
        dropoff=DROPOFF,
        speed="20",
        pause="0",
    )
    assert trip.type == "normal"
    assert [step.kind for step in trip.steps] == ["pickup", "dropoff"]
    assert trip.steps[0].point == PICKUP
    assert trip.steps[1].point == DROPOFF


def test_pooled_distinct_stops_stay_separate():
    trip = trip_from_pooled_fields(
        name="Pool",
        start=START,
        steps=[
            {"kind": "pickup", "name": "A", "point": list(PICKUP)},
            {"kind": "dropoff", "name": "A", "point": list(DROPOFF)},
        ],
        speed=20,
        pause=0,
    )
    assert len(merge_consecutive(trip.steps)) == 2


def test_shared_pickup_merges_only_that_stop():
    stops = merge_consecutive(
        (
            Step("pickup", "A", PICKUP),
            Step("pickup", "B", PICKUP),
            Step("dropoff", "A", DROPOFF),
            Step("dropoff", "B", OTHER),
        )
    )
    assert len(stops) == 3
    assert [step.name for step in stops[0].steps] == ["A", "B"]
    assert [step.kind for step in stops[0].steps] == ["pickup", "pickup"]
    assert stops[1].steps[0].name == "A"
    assert stops[2].steps[0].name == "B"


def test_shared_dropoff_merges_only_the_consecutive_dropoff():
    stops = merge_consecutive(
        (
            Step("pickup", "A", PICKUP),
            Step("pickup", "B", OTHER),
            Step("dropoff", "A", DROPOFF),
            Step("dropoff", "B", DROPOFF),
        )
    )
    assert len(stops) == 3
    assert [step.name for step in stops[2].steps] == ["A", "B"]
    assert [step.kind for step in stops[2].steps] == ["dropoff", "dropoff"]


def test_shared_pickup_and_dropoff_become_two_physical_stops():
    stops = merge_consecutive(
        (
            Step("pickup", "A", PICKUP),
            Step("pickup", "B", PICKUP),
            Step("dropoff", "A", DROPOFF),
            Step("dropoff", "B", DROPOFF),
        )
    )
    assert len(stops) == 2
    assert [(step.kind, step.name) for step in stops[0].steps] == [
        ("pickup", "A"),
        ("pickup", "B"),
    ]
    assert [(step.kind, step.name) for step in stops[1].steps] == [
        ("dropoff", "A"),
        ("dropoff", "B"),
    ]


def test_later_return_to_the_same_coordinates_is_a_new_stop():
    stops = merge_consecutive(
        (
            Step("pickup", "A", PICKUP),
            Step("dropoff", "A", DROPOFF),
            Step("pickup", "B", PICKUP),
        )
    )
    assert len(stops) == 3
    assert stops[0].point == stops[2].point == PICKUP
    assert stops[0] != stops[2]


def test_json_round_trip_normal():
    original = {
        "type": "normal",
        "name": "Passenger A",
        "start": [39.69, -105.08],
        "pickup": [39.69801, -105.070418],
        "dropoff": [39.710486, -105.064513],
        "speed_mph": 18,
        "pause_seconds": 5,
    }
    trip = trip_from_dict(original)
    assert trip_from_dict(trip_to_dict(trip)) == trip
    encoded = trip_to_dict(trip)
    assert encoded["name"] == "Passenger A"
    assert encoded["pickup"] == [39.69801, -105.070418]
    assert encoded["dropoff"] == [39.710486, -105.064513]
    assert "steps" not in encoded


def test_json_round_trip_pooled_preserves_duplicate_coordinates():
    original = {
        "type": "pooled",
        "name": "Pool A",
        "start": [39.69, -105.08],
        "steps": [
            {"kind": "pickup", "name": "A", "point": [39.69801, -105.070418]},
            {"kind": "pickup", "name": "B", "point": [39.69801, -105.070418]},
            {"kind": "dropoff", "name": "A", "point": [39.71, -105.06]},
        ],
        "speed_mph": 20,
        "pause_seconds": 0,
    }
    trip = trip_from_dict(original)
    assert trip_from_dict(trip_to_dict(trip)) == trip
    assert len(trip_to_dict(trip)["steps"]) == 3


def test_pooled_step_requires_a_passenger_name():
    with pytest.raises(ValueError, match="passenger name"):
        trip_from_pooled_fields(
            name="Pool",
            start=START,
            steps=[{"kind": "pickup", "name": "  ", "point": list(PICKUP)}],
            speed=20,
            pause=0,
        )


def test_trip_type_must_be_normal_or_pooled():
    with pytest.raises(ValueError, match="normal or pooled"):
        trip_from_dict({"type": "bus", "name": "A", "start": [0, 0]})
