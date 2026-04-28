from pathlib import Path
from typing import Optional, Tuple

import geopandas as gpd
from shapely.geometry import Point

from rental_lookup.models import LocationScore

# Central Bangalore bounding box: (west, south, east, north) for osmnx
BBOX = (77.50, 12.90, 77.70, 13.05)

# UTM zone 43N for Bangalore
UTM_CRS = "EPSG:32643"


def nearest_distance_m(
    lat: float, lng: float, features: gpd.GeoDataFrame
) -> Optional[float]:
    """Distance in meters from (lat, lng) to nearest feature.

    For best performance, pass features already projected to UTM_CRS.
    If features are in EPSG:4326, they will be reprojected per call.
    """
    if features.empty:
        return None

    point = gpd.GeoSeries([Point(lng, lat)], crs="EPSG:4326").to_crs(UTM_CRS)
    if features.crs and features.crs.to_epsg() != 32643:
        features = features.to_crs(UTM_CRS)
    distances = features.geometry.distance(point.iloc[0])
    return float(distances.min())


def compute_location_scores(
    lat: float, lng: float,
    parks: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
    metro: gpd.GeoDataFrame,
) -> LocationScore:
    return LocationScore(
        nearest_park_m=nearest_distance_m(lat, lng, parks),
        nearest_lake_m=nearest_distance_m(lat, lng, lakes),
        nearest_metro_m=nearest_distance_m(lat, lng, metro),
    )


def fetch_osm_features(cache_dir: Optional[Path] = None) -> Tuple[
    gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame
]:
    """Bulk-fetch parks, lakes, and metro for central Bangalore.
    Returns (parks_gdf, lakes_gdf, metro_gdf).
    Caches to GeoPackage if cache_dir provided.
    """
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        parks_path = cache_dir / "parks.gpkg"
        lakes_path = cache_dir / "lakes.gpkg"
        metro_path = cache_dir / "metro.gpkg"

        if parks_path.exists() and lakes_path.exists() and metro_path.exists():
            print("  Loading cached OSM data...")
            return (
                gpd.read_file(parks_path),
                gpd.read_file(lakes_path),
                gpd.read_file(metro_path),
            )

    import osmnx as ox

    print("  Fetching parks from OSM...")
    try:
        parks = ox.features_from_bbox(
            bbox=BBOX,
            tags={"leisure": ["park", "garden"], "landuse": "recreation_ground"},
        )
    except Exception as e:
        print(f"  [!] Parks fetch failed: {e}")
        parks = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    print("  Fetching lakes from OSM...")
    try:
        lakes = ox.features_from_bbox(
            bbox=BBOX,
            tags={"water": "lake"},
        )
    except Exception as e:
        print(f"  [!] Lakes fetch failed: {e}")
        lakes = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    print("  Fetching metro stations from OSM...")
    try:
        metro = ox.features_from_bbox(
            bbox=BBOX,
            tags={"network": "Namma Metro"},
        )
    except Exception as e:
        print(f"  [!] Metro fetch failed: {e}")
        metro = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    if cache_dir:
        for gdf, path in [(parks, parks_path), (lakes, lakes_path), (metro, metro_path)]:
            if not gdf.empty:
                gdf.reset_index(drop=True).to_file(path, driver="GPKG")
            else:
                gpd.GeoDataFrame(geometry=[], crs="EPSG:4326").to_file(path, driver="GPKG")

    return parks, lakes, metro
