"""Geometry helpers including point-in-polygon with optional Shapely fallback."""
from typing import List, Tuple
try:
    from shapely.geometry import Point, Polygon  # type: ignore
    _HAS_SHAPELY = True
except Exception:  # pragma: no cover
    _HAS_SHAPELY = False

PointTuple = Tuple[float, float]


def point_in_polygon(pt: PointTuple, polygon: List[PointTuple]) -> bool:
    """Return True if point inside polygon using shapely or ray casting."""
    if _HAS_SHAPELY:
        poly = Polygon(polygon)
        return poly.contains(Point(pt)) or poly.touches(Point(pt))
    # Ray casting
    x, y = pt
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if ((y1 > y) != (y2 > y)):
            xinters = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1
            if x < xinters:
                inside = not inside
    return inside
