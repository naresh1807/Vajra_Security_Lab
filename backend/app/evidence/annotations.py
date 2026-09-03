"""
Validation for screenshot markup (Section 32 "Annotate").

Annotations are non-destructive: a bounded list of simple shapes in
image-relative coordinates (0..1), stored on the attachment and rendered
over the image by the frontend. A `redact` box hides content in the app
but is only removed from the image file itself by "Flatten & replace".
"""
from __future__ import annotations

_SHAPE_TYPES = {"highlight", "redact", "arrow", "label"}
_MAX_SHAPES = 100
_MAX_TEXT_LEN = 200
_HEX_COLOR_LEN = {4, 7}  # #rgb or #rrggbb


class AnnotationError(Exception):
    pass


def _num01(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AnnotationError(f"Annotation '{field}' must be a number.")
    if not (-0.05 <= value <= 1.05):  # a little slack for edge-drawn shapes
        raise AnnotationError(f"Annotation '{field}' must be within the image (0..1).")
    return float(value)


def validate_annotations(raw: object) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AnnotationError("Annotations must be a list of shapes.")
    if len(raw) > _MAX_SHAPES:
        raise AnnotationError(f"Too many annotations (max {_MAX_SHAPES}).")

    cleaned: list[dict] = []
    for i, shape in enumerate(raw):
        if not isinstance(shape, dict):
            raise AnnotationError(f"Annotation #{i + 1} must be an object.")
        kind = shape.get("type")
        if kind not in _SHAPE_TYPES:
            raise AnnotationError(f"Annotation #{i + 1} has an unknown type: {kind!r}.")

        entry: dict = {
            "type": kind,
            "x": _num01(shape.get("x"), "x"),
            "y": _num01(shape.get("y"), "y"),
        }
        if kind == "arrow":
            entry["x2"] = _num01(shape.get("x2"), "x2")
            entry["y2"] = _num01(shape.get("y2"), "y2")
        else:
            entry["w"] = _num01(shape.get("w"), "w")
            entry["h"] = _num01(shape.get("h"), "h")

        if kind == "label":
            text = shape.get("text", "")
            if not isinstance(text, str):
                raise AnnotationError(f"Annotation #{i + 1} label text must be a string.")
            entry["text"] = text[:_MAX_TEXT_LEN]

        color = shape.get("color", "#f43f5e")
        if not isinstance(color, str) or not color.startswith("#") or len(color) not in _HEX_COLOR_LEN:
            raise AnnotationError(f"Annotation #{i + 1} color must be a hex string like #f43f5e.")
        entry["color"] = color

        cleaned.append(entry)
    return cleaned
