"""Geometry Ops (spec §7): a Mask's contours, simplified, as convex collision shapes and a navigation polygon.

Pure: arrays in, plain data out. A ring is a closed list of integer pixel corners, x right and y down. An outer ring has
a positive signed area (it runs clockwise on screen, with the Mask on its right) and a hole a negative one. All of it
works in whole numbers, so no test here can go wrong by rounding.
"""

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import numpy as np

from kiripix.ops.masks import BoolMask

Point = tuple[int, int]
Ring = list[Point]


@dataclass(frozen=True)
class Outline:
    """One piece of a Mask: its outer ring and the holes in it."""

    outer: Ring
    holes: list[Ring]

    @property
    def rings(self) -> list[Ring]:
        return [self.outer, *self.holes]


@dataclass(frozen=True)
class NavigationPolygon:
    """Convex polygons as indexes into `vertices`, each edge inside the shape shared whole by two of them, and the rings
    they fill."""

    vertices: list[Point]
    polygons: list[list[int]]
    outlines: list[Ring]


def _cross(a: Point, b: Point, c: Point) -> int:
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _doubled_area(ring: Ring) -> int:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in _edges(ring))


def _edges(ring: Ring) -> Iterator[tuple[Point, Point]]:
    return zip(ring, [*ring[1:], ring[0]])


def _boundary_edges(mask: BoolMask) -> dict[Point, list[Point]]:
    """Every pixel side between the Mask and the rest, directed with the Mask on its right, from start to ends. A corner
    where two set pixels touch only diagonally has two ways on."""
    padded = np.pad(mask, 1)
    inside = padded[1:-1, 1:-1]
    edges: dict[Point, list[Point]] = {}

    def add(sides: BoolMask, start: Point, end: Point) -> None:
        ys, xs = np.nonzero(sides)
        for y, x in zip(ys.tolist(), xs.tolist()):
            edges.setdefault((x + start[0], y + start[1]), []).append((x + end[0], y + end[1]))

    add(inside & ~padded[:-2, 1:-1], (0, 0), (1, 0))  # top
    add(inside & ~padded[1:-1, 2:], (1, 0), (1, 1))  # right
    add(inside & ~padded[2:, 1:-1], (1, 1), (0, 1))  # bottom
    add(inside & ~padded[1:-1, :-2], (0, 1), (0, 0))  # left
    return edges


def _take_edge(edges: dict[Point, list[Point]], before: Point, at: Point) -> Point:
    """Use up the way on from `at`, arriving from `before`. Where there are two, it turns towards the Mask: it stays on
    the same pixel, so pixels touching only at a corner count as apart."""
    ends = edges[at]
    towards = (at[0] - (at[1] - before[1]), at[1] + (at[0] - before[0]))
    end = towards if towards in ends else ends[0]
    ends.remove(end)
    if not ends:
        del edges[at]
    return end


def _corners(ring: Ring) -> Ring:
    """The ring without the points in the middle of a straight run."""
    return [b for a, b, c in zip([ring[-1], *ring], ring, [*ring[1:], ring[0]]) if _cross(a, b, c) != 0]


def _rings(mask: BoolMask) -> list[Ring]:
    edges = _boundary_edges(mask)
    rings = []
    for start in sorted(edges, key=lambda point: (point[1], point[0])):
        while start in edges:
            ring = [start]
            at = _take_edge(edges, start, start)
            while at != start:
                ring.append(at)
                at = _take_edge(edges, ring[-2], at)
            rings.append(_corners(ring))
    return rings


def _contains(ring: Ring, x: float, y: float) -> bool:
    inside = False
    for a, b in _edges(ring):
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            inside = not inside
    return inside


def contours(mask: BoolMask) -> list[Outline]:
    """The Mask's outlines, along pixel edges, each with its holes: top-left first, and a piece with its holes before any
    piece inside them. Pixels touching only at a corner are apart, so a hole can touch its outer ring only by merging
    into it: that ring then passes through the corner twice."""
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    rings = _rings(mask)
    outers = [ring for ring in rings if _doubled_area(ring) > 0]
    holes: dict[int, list[Ring]] = {index: [] for index in range(len(outers))}
    for hole in (ring for ring in rings if _doubled_area(ring) < 0):
        # The Mask's pixel beside the hole's first edge is in the piece around the hole, and the smallest outer ring around
        # that pixel is that piece's.
        (ax, ay), (bx, by) = hole[0], hole[1]
        dx, dy = (bx > ax) - (bx < ax), (by > ay) - (by < ay)
        x, y = ax + (dx - dy) / 2, ay + (dy + dx) / 2
        around = (index for index, outer in enumerate(outers) if _contains(outer, x, y))
        holes[min(around, key=lambda index: _doubled_area(outers[index]))].append(hole)
    return [Outline(outer, holes[index]) for index, outer in enumerate(outers)]


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    along = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) if length else 0.0
    return math.hypot(point[0] - a[0] - along * dx, point[1] - a[1] - along * dy)


def _douglas_peucker(points: Ring, tolerance: float) -> Ring:
    """The run from its first point to its last with what stays within `tolerance` of a straight line left out."""
    keep = {0, len(points) - 1}
    pending = [(0, len(points) - 1)]
    while pending:
        first, last = pending.pop()
        if last - first < 2:
            continue
        farthest = max(range(first + 1, last), key=lambda i: _distance_to_segment(points[i], points[first], points[last]))
        if _distance_to_segment(points[farthest], points[first], points[last]) > tolerance:
            keep.add(farthest)
            pending += [(first, farthest), (farthest, last)]
    return [points[index] for index in sorted(keep)]


def _simplified_ring(ring: Ring, tolerance: float) -> Ring:
    """Split at the point farthest from the first, since a closed ring has no straight line to measure from."""
    opposite = max(range(len(ring)), key=lambda i: math.dist(ring[0], ring[i]))
    there = _douglas_peucker(ring[:opposite + 1], tolerance)
    back = _douglas_peucker([*ring[opposite:], ring[0]], tolerance)
    return [*there, *back[1:-1]]


def _segments_touch(a: Point, b: Point, c: Point, d: Point) -> bool:
    def side(p: Point, q: Point, r: Point) -> int:
        return (_cross(p, q, r) > 0) - (_cross(p, q, r) < 0)

    def within(p: Point, q: Point, r: Point) -> bool:
        return min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])

    ab_c, ab_d, cd_a, cd_b = side(a, b, c), side(a, b, d), side(c, d, a), side(c, d, b)
    if ab_c != ab_d and cd_a != cd_b:
        return True
    return (ab_c == 0 and within(a, b, c) or ab_d == 0 and within(a, b, d) or
            cd_a == 0 and within(c, d, a) or cd_b == 0 and within(c, d, b))


def _is_clean(rings: list[Ring]) -> bool:
    """Whether the rings are each a real shape, with no two edges meeting except where a ring goes on from one to the
    next."""
    if any(len(ring) < 3 or _doubled_area(ring) == 0 for ring in rings):
        return False
    edges = [(ring_index, index, a, b) for ring_index, ring in enumerate(rings) for index, (a, b) in enumerate(_edges(ring))]
    sizes = [len(ring) for ring in rings]
    for position, (ring_a, index_a, a, b) in enumerate(edges):
        for ring_b, index_b, c, d in edges[position + 1:]:
            if ring_a == ring_b and (index_b - index_a) % sizes[ring_a] in (1, sizes[ring_a] - 1):
                continue
            if _segments_touch(a, b, c, d):
                return False
    return True


def simplify(outlines: Iterable[Outline], tolerance: float) -> list[Outline]:
    """Douglas-Peucker on every ring, keeping corners more than `tolerance` px off the straight line. An outline this
    would break (a ring gone flat, or rings that now touch or cross) stays as it was."""
    if tolerance < 0:
        raise ValueError(f"a tolerance can't be negative, got {tolerance}")
    result = []
    for outline in outlines:
        rings = [_simplified_ring(ring, tolerance) for ring in outline.rings]
        result.append(Outline(rings[0], rings[1:]) if _is_clean(rings) else outline)
    return result


def _in_cone(previous: Point, at: Point, following: Point, target: Point) -> bool:
    """Whether a line from `at` to `target` starts inside the shape, at a corner between those neighbours."""
    if _cross(previous, at, following) >= 0:
        return _cross(at, target, previous) > 0 and _cross(target, at, following) > 0
    return not (_cross(at, target, following) >= 0 and _cross(target, at, previous) >= 0)


def _bridge(polygon: Ring, hole: Ring, others: list[Ring]) -> Ring:
    """Cut from the hole to the polygon, along a line that touches nothing: the two become one ring that passes along the
    cut twice. The rightmost corners of the hole are tried first, each to the nearest corner it can see."""
    obstacles = [(a, b) for ring in (polygon, hole, *others) for a, b in _edges(ring)]
    for start in sorted(range(len(hole)), key=lambda i: (-hole[i][0], hole[i][1])):
        at = hole[start]
        before, after = hole[start - 1], hole[(start + 1) % len(hole)]
        by_distance = sorted(range(len(polygon)), key=lambda i: (math.dist(polygon[i], at), i))
        for index in by_distance:
            target = polygon[index]
            if not _in_cone(before, at, after, target):
                continue
            if not _in_cone(polygon[index - 1], target, polygon[(index + 1) % len(polygon)], at):
                continue
            if any(_segments_touch(at, target, a, b) and not {a, b} & {at, target} for a, b in obstacles):
                continue
            around = [*hole[start:], *hole[:start]]
            return [*polygon[:index + 1], *around, at, target, *polygon[index + 1:]]
    raise ValueError("a hole can't be joined to its outer ring")


def _inside_triangle(a: Point, b: Point, c: Point, point: Point) -> bool:
    return _cross(a, b, point) >= 0 and _cross(b, c, point) >= 0 and _cross(c, a, point) >= 0


def _triangles(polygon: Ring) -> list[Ring]:
    """Ear clipping. Corners passed twice (a cut, or a pinch) sit on top of each other, so a corner at the same place as
    the ear's is no obstacle, but the ear's new edge then mustn't run into any edge."""
    remaining = list(polygon)
    triangles: list[Ring] = []
    while len(remaining) > 3:
        size = len(remaining)
        for index in range(size):
            a, b, c = remaining[index - 1], remaining[index], remaining[(index + 1) % size]
            if _cross(a, b, c) <= 0:
                continue
            blocked = shared = False
            for offset in range(2, size - 1):
                other = remaining[(index + offset) % size]
                if other in (a, b, c):
                    shared = True
                elif _inside_triangle(a, b, c, other):
                    blocked = True
                    break
            if blocked or shared and not _clear_diagonal(remaining, index):
                continue
            triangles.append([a, b, c])
            del remaining[index]
            break
        else:
            # No ear: drop what has no area (a spike along a cut, or a corner in a straight run).
            flat = next((i for i in range(size) if _cross(remaining[i - 1], remaining[i], remaining[(i + 1) % size]) == 0),
                        None)
            if flat is None:
                raise ValueError("a shape can't be cut into triangles")
            del remaining[flat]
    if len(remaining) == 3 and _cross(*remaining) > 0:
        triangles.append(remaining)
    return triangles


def _clear_diagonal(polygon: Ring, index: int) -> bool:
    """Whether the edge that clipping the corner `index` would make crosses nothing, and starts inside the shape at both
    ends, where corners on top of each other can each have edges of their own."""
    size = len(polygon)
    a, c = polygon[index - 1], polygon[(index + 1) % size]
    for position, (p, q) in enumerate(_edges(polygon)):
        if position in ((index - 2) % size, (index - 1) % size, index, (index + 1) % size):
            continue
        if not {p, q} & {a, c} and _segments_touch(a, c, p, q):
            return False
        if p in (a, c) and _cross(a, c, q) > 0 and _inside_triangle(a, polygon[index], c, q):
            return False
    return True


def _merged(first: Ring, second: Ring, a: Point, b: Point) -> Ring | None:
    """The two polygons, which share the edge a to b, as one if it stays convex; else None."""
    start, end = first.index(b), second.index(a)
    there = [*first[start:], *first[:start]]
    back = [*second[end:], *second[:end]]
    for before, at, after in ((there[-2], a, back[1]), (back[-2], b, there[1])):
        turn = _cross(before, at, after)
        if turn < 0 or turn == 0 and (at[0] - before[0]) * (after[0] - at[0]) + (at[1] - before[1]) * (after[1] - at[1]) <= 0:
            return None
    return [*there, *back[1:-1]]


def _convex_pieces(outline: Outline) -> list[Ring]:
    """Triangles of the outline, merged across shared edges while they stay convex. An edge is never split, so polygons
    next to each other still share theirs whole, keeping a corner in a straight run where a neighbour needs it."""
    polygon = outline.outer
    holes = sorted(outline.holes, key=lambda hole: (-max(x for x, _ in hole), min(y for _, y in hole)))
    for index, hole in enumerate(holes):
        polygon = _bridge(polygon, hole, holes[index + 1:])
    pieces = dict(enumerate(_triangles(polygon)))
    owner = {edge: key for key, piece in pieces.items() for edge in _edges(piece)}
    for key in list(pieces):
        if key not in pieces:
            continue
        merging = True
        while merging:
            merging = False
            for a, b in _edges(pieces[key]):
                other = owner.get((b, a))
                if other is None or other == key or other not in pieces:
                    continue
                merged = _merged(pieces[key], pieces[other], a, b)
                if merged is None:
                    continue
                for edge in _edges(pieces.pop(other)):
                    owner[edge] = key
                del owner[(a, b)], owner[(b, a)]
                pieces[key] = merged
                merging = True
                break
    return [_from_top_left(piece) for piece in pieces.values()]


def _from_top_left(piece: Ring) -> Ring:
    start = min(range(len(piece)), key=lambda i: (piece[i][1], piece[i][0]))
    return [*piece[start:], *piece[:start]]


def collision_shapes(outlines: Iterable[Outline]) -> list[Ring]:
    """Convex polygons that together cover the outlines exactly, since a collision polygon can't have a hole."""
    return [piece for outline in outlines for piece in _convex_pieces(outline)]


def navigation_polygon(outlines: Iterable[Outline]) -> NavigationPolygon:
    """The outlines as a navigation mesh: convex polygons that share their edges and vertices exactly."""
    listed = list(outlines)
    vertices: dict[Point, int] = {}
    polygons = [[vertices.setdefault(point, len(vertices)) for point in piece] for piece in collision_shapes(listed)]
    return NavigationPolygon(list(vertices), polygons, [ring for outline in listed for ring in outline.rings])
