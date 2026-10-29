"""Pure selection-to-screen mapping and one-time anchor choice; no AX/Qt I/O."""
import math
from rat.ui.mini_placement import Rect, place_look, LOOK_WIDTH, LOOK_HEIGHT, FLOAT_HEAD_SIZE


def map_selection(context, full_screen):
    try:
        x,y,w,h = (float(v) for v in context['rect'])
        dx,dy,dw,dh = (float(v) for v in context['display'])
        if not all(math.isfinite(v) for v in (x,y,w,h,dx,dy,dw,dh)) or min(w,h,dw,dh) <= 0:
            return None
        left = max(full_screen.x, full_screen.x+(x-dx)*full_screen.width/dw)
        top = max(full_screen.y, full_screen.y+(y-dy)*full_screen.height/dh)
        right = min(full_screen.right, full_screen.x+(x+w-dx)*full_screen.width/dw)
        bottom = min(full_screen.bottom, full_screen.y+(y+h-dy)*full_screen.height/dh)
        return Rect(round(left),round(top),round(right-left),round(bottom-top)) if right>left and bottom>top else None
    except (KeyError, TypeError, ValueError):
        return None


def choose_selection_home(available, selection, width, height):
    size, gap = FLOAT_HEAD_SIZE, 12
    candidates = ((selection.right+gap,selection.y,'right'),
        (selection.x-gap-size,selection.y,'left'),
        (selection.x,selection.bottom+gap,'bottom'),
        (selection.x,selection.y-gap-size,'top'))
    scored=[]
    for x,y,side in candidates:
        home=(x-LOOK_WIDTH+size,y-LOOK_HEIGHT+size)
        placed=place_look(available,home,width,height,side=side,floating_head=True)
        body=placed.panel
        overlap=max(0,min(body.right,selection.right)-max(body.x,selection.x))*max(0,min(body.bottom,selection.bottom)-max(body.y,selection.y))
        distance=abs(placed.rat.x-x)+abs(placed.rat.y-y)
        scored.append(((overlap>0,overlap,distance),home,placed.side))
    _,home,side=min(scored,key=lambda row:row[0])
    return home,side
