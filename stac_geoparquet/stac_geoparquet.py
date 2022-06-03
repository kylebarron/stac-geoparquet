"""
Generate geoparquet from a sequence of STAC items.
"""
from __future__ import annotations
from collections import namedtuple

from typing import Sequence, Any, TypedDict

import pystac
import geopandas
import pandas as pd
import shapely.geometry


class ItemLike(TypedDict):
    type: str
    stac_version: str
    stac_extensions: list[str]
    id: str
    geometry: dict[str, Any] | None
    bbox: list[float] | None
    properties: dict[str, Any]
    links: list[dict[str, Any]]
    assets: dict[str, Any]
    collection: str | None


def to_geodataframe(items: Sequence[ItemLike]) -> geopandas.GeoDataFrame:
    """
    Convert a sequence of STAC items to a :class:`geopandas.GeoDataFrame`.

    The objects under `properties` are moved up to the top-level of the
    DataFrame, similar to :meth:`geopandas.GeoDataFrame.from_features`.

    Parameters
    ----------
    items: A sequence of STAC items.

    Returns
    -------
    The converted GeoDataFrame.
    """
    items2 = []
    for item in items:
        item2 = {k: v for k, v in item.items() if k != "properties"}
        for k, v in item["properties"].items():
            if k in item2:
                raise ValueError("k", k)
            item2[k] = v
        items2.append(item2)

    # Filter out missing geoms in MultiPolygons
    # https://github.com/shapely/shapely/issues/1407
    # geometry = [shapely.geometry.shape(x["geometry"]) for x in items2]

    geometry = []
    for item in items2:
        item_geom = item["geometry"]
        if item_geom["type"] == "MultiPolygon":
            item_geom = dict(item_geom)
            item_geom["coordinates"] = [x for x in item_geom["coordinates"] if any(x)]
        geometry.append(shapely.geometry.shape(item_geom))

    gdf = geopandas.GeoDataFrame(items2, geometry=geometry, crs="WGS84")

    for column in ["datetime", "start_datetime", "end_datetime"]:
        if column in gdf.columns:
            gdf[column] = pd.to_datetime(gdf[column])

    columns = [
        "type",
        "stac_version",
        "stac_extensions",
        "id",
        "geometry",
        "bbox",
        "links",
        "assets",
        "collection",
    ]
    gdf = pd.concat([gdf[columns], gdf.drop(columns=columns)], axis="columns")
    for k in ["type", "stac_version", "id", "collection"]:
        gdf[k] = gdf[k].astype("string")

    return gdf


def to_dict(row: namedtuple):
    """
    Create a dictionary representing a STAC item from a row of the GeoDataFrame.

    Parameters
    ----------
    row: namedtuple
    """
    keys = {
        "type",
        "stac_version",
        "id",
        "geometry",
        "bbox",
        "links",
        "assets",
        "collection",
    }
    item = row._asdict()
    item["datetime"] = item["datetime"].isoformat()
    out = {"properties": {}}
    for k, v in item.items():
        if k in keys:
            out[k] = v
        else:
            out["properties"][k] = v
    return out


def to_item_collection(df):
    return pystac.ItemCollection([to_dict(row) for row in df.itertuples(index=False)])
