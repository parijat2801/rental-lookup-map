"""OpenStreetMap features (parks, lakes, metro, woods) and distance-to-nearest lookups."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from pyproj import CRS, Transformer
from shapely.geometry import Point

from rental_lookup.models import NearbyDistances

# Bounding box as (west, south, east, north), osmnx 2.x order. Must enclose every
# NoBroker search anchor plus its ~2 km radius (Kadugodi east, Sarjapura south).
BANGALORE_BBOX = (77.50, 12.83, 77.81, 13.05)
LAT_LNG_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:32643"  # UTM zone 43N: metre-based CRS covering Bangalore

# Bump when the fetch or post-filtering changes, to invalidate cached GeoPackages.
OSM_CACHE_VERSION = 4
# Stick to tags that mean a real public green space. leisure=garden, recreation_ground,
# scrub, tree_row and orchard are everywhere in Bangalore OSM and made every listing look leafy.
OSM_FEATURE_TAGS = {
    "parks": {"leisure": ["park", "nature_reserve"]},
    "lakes": {"water": "lake"},
    "metro": {"network": "Namma Metro"},
    "woods": {"natural": "wood", "landuse": "forest"},
}
# Drop pocket parks / tiny scrub patches; only count neighbourhood-scale greenery.
# Metro is points — no area filter.
MIN_FEATURE_AREA_M2 = {
    "parks": 5_000,   # ~0.5 ha
    "lakes": 10_000,  # ~1 ha
    "woods": 10_000,
    "metro": 0,
}


@lru_cache(maxsize=1)
def _lat_lng_to_metric() -> Transformer:
    return Transformer.from_crs(LAT_LNG_CRS, METRIC_CRS, always_xy=True)


def to_metric_crs(features: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project to metres unless already projected, empty, or CRS-less (assumed projected)."""
    if features.empty or features.crs is None or CRS(features.crs) == CRS(METRIC_CRS):
        return features
    return features.to_crs(METRIC_CRS)


def nearest_distance_m(lat: float, lng: float, features: gpd.GeoDataFrame) -> Optional[float]:
    """Distance in metres from (lat, lng) to the nearest feature; None if there are none.

    Pass features already projected with `to_metric_crs` to avoid re-projecting per call.
    """
    if features.empty:
        return None
    point = Point(_lat_lng_to_metric().transform(float(lng), float(lat)))
    return float(to_metric_crs(features).geometry.distance(point).min())


def measure_nearby_distances(
    lat: float, lng: float,
    parks: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
    metro_stations: gpd.GeoDataFrame,
    woods: Optional[gpd.GeoDataFrame] = None,
) -> NearbyDistances:
    return NearbyDistances(
        nearest_park_m=nearest_distance_m(lat, lng, parks),
        nearest_lake_m=nearest_distance_m(lat, lng, lakes),
        nearest_woods_m=nearest_distance_m(lat, lng, woods) if woods is not None else None,
        nearest_metro_m=nearest_distance_m(lat, lng, metro_stations),
    )


def _empty_features() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[], crs=LAT_LNG_CRS)


def filter_by_min_area(
    features: gpd.GeoDataFrame,
    min_area_m2: float,
) -> gpd.GeoDataFrame:
    """Keep polygons at least `min_area_m2`; drop points/lines. No-op when min is 0.

    Returns features in LAT_LNG_CRS so they match what we cache and what callers expect.
    """
    if features.empty or min_area_m2 <= 0:
        return features
    metric = to_metric_crs(features)
    keep = metric.geom_type.isin(["Polygon", "MultiPolygon"]) & (metric.geometry.area >= min_area_m2)
    filtered = metric.loc[keep, ["geometry"]]
    if filtered.empty:
        return _empty_features()
    return filtered.to_crs(LAT_LNG_CRS).reset_index(drop=True)


def operating_stations(features: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep only open metro stations.

    `network=Namma Metro` also matches track, platforms, entrances and stations
    that are proposed or under construction, which would make every listing near
    a future line look metro-adjacent.
    """
    def tag(name: str) -> pd.Series:
        return features[name] if name in features else pd.Series(None, index=features.index, dtype=object)

    is_station = (tag("railway") == "station") | (tag("public_transport") == "station")
    for lifecycle_tag in ("construction", "proposed", "disused", "abandoned"):
        is_station &= tag(lifecycle_tag).isna()
    is_station &= ~tag("name").fillna("").astype(str).str.contains(r"u/c|proposed", case=False)
    return features[is_station]


def _write_feature_cache(path: Path, features: gpd.GeoDataFrame) -> None:
    """Atomic GeoPackage write so an interrupted run never leaves a corrupt file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.stem + ".tmp.gpkg")
    temp_path.unlink(missing_ok=True)
    features.to_file(temp_path, driver="GPKG")
    temp_path.replace(path)


def fetch_osm_features(
    cache_dir: Optional[Path] = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Bulk-fetch (parks, lakes, metro stations, woods) within BANGALORE_BBOX.

    Each layer is cached on its own (bbox + OSM_CACHE_VERSION in the filename), so a
    transient Overpass failure on one tag doesn't force refetching the others. A
    failed fetch yields an empty frame and is not cached, so the next run retries it.
    """
    bbox_tag = "_".join(f"{coordinate:.2f}" for coordinate in BANGALORE_BBOX)
    cache_paths = ({name: cache_dir / f"{name}_{bbox_tag}_v{OSM_CACHE_VERSION}.gpkg" for name in OSM_FEATURE_TAGS}
                   if cache_dir else {})

    layers = {}
    ox = None  # lazy-import only if a layer still needs fetching
    for name, tags in OSM_FEATURE_TAGS.items():
        cache_path = cache_paths.get(name)
        if cache_path and cache_path.exists():
            print(f"  Loading cached {name}...")
            layers[name] = gpd.read_file(cache_path)
            continue

        if ox is None:
            import osmnx as ox  # heavy import, only needed on a cache miss

        print(f"  Fetching {name} from OSM...")
        try:
            # Only geometry is used; OSM attribute columns (lists, mixed types) can break GPKG writes.
            features = ox.features_from_bbox(bbox=BANGALORE_BBOX, tags=tags)
            if name == "metro":
                features = operating_stations(features)
            features = features[["geometry"]].reset_index(drop=True)
            before = len(features)
            features = filter_by_min_area(features, MIN_FEATURE_AREA_M2[name])
            if before and before != len(features):
                print(f"    kept {len(features)}/{before} after >={MIN_FEATURE_AREA_M2[name]} m² filter")
            layers[name] = features
            if cache_path:
                _write_feature_cache(cache_path, features)
        except Exception as e:  # osmnx raises a variety of network / "no data" errors
            print(f"  [!] {name.capitalize()} fetch failed: {e}")
            layers[name] = _empty_features()

    return layers["parks"], layers["lakes"], layers["metro"], layers["woods"]
