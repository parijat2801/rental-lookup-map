"""OpenStreetMap features (parks, lakes, metro) and distance-to-nearest lookups."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry import Point

from rental_lookup.models import NearbyDistances

# Central Bangalore bounding box as (west, south, east, north), osmnx 2.x order.
CENTRAL_BANGALORE_BBOX = (77.50, 12.90, 77.70, 13.05)
LAT_LNG_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:32643"  # UTM zone 43N: metre-based CRS covering Bangalore

OSM_FEATURE_TAGS = {
    "parks": {"leisure": ["park", "garden"], "landuse": "recreation_ground"},
    "lakes": {"water": "lake"},
    "metro": {"network": "Namma Metro"},
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
) -> NearbyDistances:
    return NearbyDistances(
        nearest_park_m=nearest_distance_m(lat, lng, parks),
        nearest_lake_m=nearest_distance_m(lat, lng, lakes),
        nearest_metro_m=nearest_distance_m(lat, lng, metro_stations),
    )


def _empty_features() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[], crs=LAT_LNG_CRS)


def fetch_osm_features(
    cache_dir: Optional[Path] = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Bulk-fetch (parks, lakes, metro stations) for central Bangalore.

    Cached as GeoPackages in `cache_dir` when given. A failed fetch yields an
    empty frame, so scoring degrades gracefully instead of crashing.
    """
    cache_paths = {name: cache_dir / f"{name}.gpkg" for name in OSM_FEATURE_TAGS} if cache_dir else {}
    if cache_paths and all(path.exists() for path in cache_paths.values()):
        print("  Loading cached OSM data...")
        return tuple(gpd.read_file(cache_paths[name]) for name in OSM_FEATURE_TAGS)

    import osmnx as ox  # heavy import, only needed on a cache miss

    layers, any_failed = {}, False
    for name, tags in OSM_FEATURE_TAGS.items():
        print(f"  Fetching {name} from OSM...")
        try:
            # Only geometry is used; OSM attribute columns (lists, mixed types) can break GPKG writes.
            features = ox.features_from_bbox(bbox=CENTRAL_BANGALORE_BBOX, tags=tags)
            layers[name] = features[["geometry"]].reset_index(drop=True)
        except Exception as e:  # osmnx raises a variety of network / "no data" errors
            print(f"  [!] {name.capitalize()} fetch failed: {e}")
            layers[name], any_failed = _empty_features(), True

    # Don't cache a partial result, or a transient failure would stick forever.
    if cache_paths and not any_failed:
        cache_dir.mkdir(parents=True, exist_ok=True)
        for name, features in layers.items():
            # Write-then-rename so an interrupted run never leaves a corrupt GeoPackage.
            temp_path = cache_paths[name].with_name(f"{name}.tmp.gpkg")
            temp_path.unlink(missing_ok=True)
            features.to_file(temp_path, driver="GPKG")
            temp_path.replace(cache_paths[name])

    return layers["parks"], layers["lakes"], layers["metro"]
