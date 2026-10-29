"""Place a speech body around an anchor without moving the anchor or running tools."""
from dataclasses import dataclass
from rat.ui.surface_geometry import Rect


@dataclass(frozen=True)
class SpeechPlacement:
    body: Rect
    bounds: Rect
    side: str


def place_speech(available, anchor, width, height, *, preferred_side=None, gap=12, margin=16, anchor_point=None, align_bottom=False, preserve_side=False):
    """Keep a fitting side, otherwise choose another; shrink only when necessary.

    The caller owns anchor placement and side memory. Coordinates are logical
    pixels on any display, including displays with negative origins.
    """
    left, top = available.x+margin, available.y+margin
    right, bottom = max(left+1, available.right-margin), max(top+1, available.bottom-margin)
    width, height = max(1, min(round(width), right-left)), max(1, min(round(height), bottom-top))
    capacities = {
        'left': (max(0, anchor.x-gap-left), bottom-top),
        'right': (max(0, right-anchor.right-gap), bottom-top),
        'top': (right-left, max(0, anchor.y-gap-top)),
        'bottom': (right-left, max(0, bottom-anchor.bottom-gap)),
    }
    order = list(dict.fromkeys([preferred_side, 'left', 'right', 'top', 'bottom']))
    order = [side for side in order if side in capacities]
    side = next((side for side in order if capacities[side][0] >= width and capacities[side][1] >= height), None)
    if (preserve_side and preferred_side in capacities
            and capacities[preferred_side][0] >= min(width, 160)
            and capacities[preferred_side][1] >= min(height, 72)):
        # Keep the user's reading side and rewrap inside it before relocating
        # the surface. Only an unusable strip forces a side change.
        side = preferred_side
        width = min(width, capacities[side][0])
        height = min(height, capacities[side][1])
    if side is None:
        side = max(order, key=lambda name: min(width, capacities[name][0])*min(height, capacities[name][1]))
        width = max(1, min(width, capacities[side][0]))
        height = max(1, min(height, capacities[side][1]))
    x = round(anchor.x+(anchor.width-width)/2)
    # Corner companions grow their speech upward from a shared baseline rather
    # than moving both edges around the mouth whenever the text length changes.
    y = round(anchor.bottom-height if align_bottom else
              (anchor_point[1] if anchor_point else anchor.y+anchor.height/2) - height/2)
    if side == 'left':
        x = anchor.x-gap-width
    elif side == 'right':
        x = anchor.right+gap
    elif side == 'top':
        y = anchor.y-gap-height
    else:
        y = anchor.bottom+gap
    body = Rect(max(left, min(x, right-width)), max(top, min(y, bottom-height)), width, height)
    return SpeechPlacement(body, body.union(anchor), side)
