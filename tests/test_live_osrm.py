"""One real OSRM request. Skipped unless NAVEERA_LIVE_OSRM=1."""

import os

import pytest

from naveera_gpx.data.osrm import OsrmRouter

pytestmark = pytest.mark.live


def test_live_osrm_returns_a_road_geometry():
    if os.environ.get("NAVEERA_LIVE_OSRM") != "1":
        pytest.skip("set NAVEERA_LIVE_OSRM=1 to contact the public OSRM server")
    route = OsrmRouter().route((39.690000, -105.080000), (39.698010, -105.070418))
    assert route.distance_meters > 50
    assert len(route.points) > 2
