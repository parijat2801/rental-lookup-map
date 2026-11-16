import geopandas as gpd
from shapely.geometry import Point, Polygon

from rental_lookup.location import measure_nearby_distances, nearest_distance_m
from rental_lookup.models import NearbyDistances


def _make_point_gdf(coords):
    """Build GeoDataFrame from (lat, lng) pairs."""
    points = [Point(lng, lat) for lat, lng in coords]
    return gpd.GeoDataFrame(geometry=points, crs="EPSG:4326")


def test_nearest_distance_to_single_point():
    parks = _make_point_gdf([(12.9829, 77.6408)])
    dist = nearest_distance_m(12.9784, 77.6408, parks)
    assert dist is not None
    assert 400 < dist < 600


def test_nearest_distance_picks_closest():
    parks = _make_point_gdf([
        (12.9829, 77.6408),
        (12.9900, 77.6408),
    ])
    dist = nearest_distance_m(12.9784, 77.6408, parks)
    assert dist is not None
    assert dist < 600


def test_nearest_distance_empty_gdf():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    dist = nearest_distance_m(12.97, 77.64, empty)
    assert dist is None


def test_nearest_distance_to_polygon():
    """Real OSM parks/lakes are polygons, not points. Test distance to polygon."""
    # A rectangular park near the listing
    park_polygon = Polygon([
        (77.640, 12.980), (77.642, 12.980),
        (77.642, 12.982), (77.640, 12.982),
    ])
    parks = gpd.GeoDataFrame(geometry=[park_polygon], crs="EPSG:4326")
    dist = nearest_distance_m(12.9784, 77.6408, parks)
    assert dist is not None
    assert dist < 300  # should be close to the polygon edge


def test_compute_location_scores():
    parks = _make_point_gdf([(12.9829, 77.6408)])
    lakes = _make_point_gdf([(12.9600, 77.6400)])
    metro = _make_point_gdf([(12.9784, 77.6350)])
    woods = _make_point_gdf([(12.9790, 77.6410)])

    score = measure_nearby_distances(12.9784, 77.6408, parks, lakes, metro, woods)
    assert isinstance(score, NearbyDistances)
    assert score.nearest_park_m is not None
    assert 400 < score.nearest_park_m < 600
    assert score.nearest_lake_m is not None
    assert score.nearest_lake_m > 1500
    assert score.nearest_woods_m is not None
    assert score.nearest_woods_m < 200
    assert score.nearest_metro_m is not None
    assert 500 < score.nearest_metro_m < 700


def test_compute_location_scores_no_data():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    score = measure_nearby_distances(12.97, 77.64, empty, empty, empty, empty)
    assert score.nearest_park_m is None
    assert score.nearest_lake_m is None
    assert score.nearest_woods_m is None
    assert score.nearest_metro_m is None


def test_compute_location_scores_woods_optional():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    score = measure_nearby_distances(12.97, 77.64, empty, empty, empty)
    assert score.nearest_woods_m is None


def test_osm_bbox_covers_every_search_anchor():
    from rental_lookup.location import BANGALORE_BBOX
    from rental_lookup.sources.nobroker import NEIGHBORHOODS

    west, south, east, north = BANGALORE_BBOX
    margin = 0.018  # ~2 km, the NoBroker search radius
    for name, anchor in NEIGHBORHOODS.items():
        assert west + margin <= anchor["lon"] <= east - margin, name
        assert south + margin <= anchor["lat"] <= north - margin, name


def test_operating_stations_drops_track_and_unbuilt_stations():
    from rental_lookup.location import operating_stations

    features = gpd.GeoDataFrame({
        "name": ["Indiranagar", "Prestige Bellandur (u/c)", "Kaikondrahalli", "Phase 2A", "Hoodi"],
        "railway": ["station", None, None, "subway", None],
        "public_transport": ["station", None, None, None, "station"],
        "construction": [None, "station", None, None, None],
        "proposed": [None, None, "station", None, None],
    }, geometry=[Point(77.64, 12.97)] * 5, crs="EPSG:4326")

    assert list(operating_stations(features)["name"]) == ["Indiranagar", "Hoodi"]


def test_filter_by_min_area_drops_pocket_parks_and_points():
    from rental_lookup.location import METRIC_CRS, filter_by_min_area

    # ~50x50 m pocket (~2500 m²) vs ~100x100 m neighbourhood park (~10000 m²), in metres.
    pocket = Polygon([(0, 0), (50, 0), (50, 50), (0, 50)])
    real = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    features = gpd.GeoDataFrame(
        geometry=[pocket, real, Point(10, 10)],
        crs=METRIC_CRS,
    )
    kept = filter_by_min_area(features, 5_000)
    assert len(kept) == 1
    assert kept.crs.to_string() == "EPSG:4326"


def test_filter_by_min_area_noop_when_zero():
    from rental_lookup.location import filter_by_min_area

    features = _make_point_gdf([(12.97, 77.64)])
    assert len(filter_by_min_area(features, 0)) == 1
