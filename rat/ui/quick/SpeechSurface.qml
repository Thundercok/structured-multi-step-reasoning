import QtQuick

// Shared visual shell. Children own reading/input; this surface runs no tools.
Item {
    id: surface
    property real padding: 14
    property real cornerRadius: 18
    property real tailLength: 18
    property bool tailEnabled: true
    // Shared size vocabulary for the corner composer and reader. Screen
    // clamping can still make the actual surface narrower than these tiers.
    property var widthSteps: [220, 380, 580]
    property real heldWidth: 0
    property real heldHeight: 0
    property point anchorPoint: Qt.point(width + 24, height / 2)
    property color paperColor: "#fdfefb"
    property color edgeColor: "#dce3d4"
    property color inkColor: "#2c302a"
    property color selectionColor: "#dbe7d1"
    readonly property bool hasTail: tailEnabled && (anchorPoint.x < 0 || anchorPoint.x > width || anchorPoint.y < 0 || anchorPoint.y > height)
    readonly property string tailSide: anchorPoint.x < 0 ? "left" : anchorPoint.x > width ? "right" : anchorPoint.y < 0 ? "top" : "bottom"
    readonly property point tailBase: {
        var inset = cornerRadius + 5
        var cx = Math.max(Math.min(inset, width / 2), Math.min(anchorPoint.x, Math.max(width / 2, width - inset)))
        var cy = Math.max(Math.min(inset, height / 2), Math.min(anchorPoint.y, Math.max(height / 2, height - inset)))
        return tailSide === "left" ? Qt.point(0, cy) : tailSide === "right" ? Qt.point(width, cy)
            : tailSide === "top" ? Qt.point(cx, 0) : Qt.point(cx, height)
    }
    readonly property point tailTip: {
        var dx = anchorPoint.x - tailBase.x, dy = anchorPoint.y - tailBase.y
        var distance = Math.max(1, Math.sqrt(dx * dx + dy * dy))
        var reach = Math.min(tailLength, distance)
        return Qt.point(tailBase.x + dx / distance * reach, tailBase.y + dy / distance * reach)
    }
    // Includes the tail so an external window mask cannot clip it.
    readonly property rect occupiedRect: !hasTail ? Qt.rect(0, 0, width, height) : Qt.rect(Math.min(0, tailTip.x), Math.min(0, tailTip.y),
        Math.max(width, tailTip.x) - Math.min(0, tailTip.x), Math.max(height, tailTip.y) - Math.min(0, tailTip.y))

    function widthStepFor(required, maximum) {
        for (var i = 0; i < widthSteps.length; ++i)
            if (required <= widthSteps[i]) return Math.min(maximum, widthSteps[i])
        return maximum
    }
    function holdSize(w, h) { heldWidth = w; heldHeight = h }
    function releaseSize() { heldWidth = 0; heldHeight = 0 }

    function repaintTail() { if (tail.available) tail.requestPaint() }
    onTailTipChanged: repaintTail()
    onTailBaseChanged: repaintTail()
    onPaperColorChanged: repaintTail()
    onEdgeColorChanged: repaintTail()
    onHasTailChanged: repaintTail()
    onWidthChanged: repaintTail()
    onHeightChanged: repaintTail()
    Rectangle {
        anchors.fill: parent; radius: surface.cornerRadius
        color: surface.paperColor; border.color: surface.edgeColor
    }
    Canvas {
        id: tail
        x: -surface.tailLength; y: -surface.tailLength
        width: surface.width + 2 * surface.tailLength; height: surface.height + 2 * surface.tailLength
        onAvailableChanged: { if (available) requestPaint() }
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            if (!surface.hasTail) return
            ctx.translate(surface.tailLength, surface.tailLength)
            var b = surface.tailBase, t = surface.tailTip
            var vertical = surface.tailSide === "left" || surface.tailSide === "right"
            var dx = vertical ? 0 : 5, dy = vertical ? 5 : 0
            // Cover the body's border at the join; stroke only the two outer edges.
            var inwardX = surface.tailSide === "left" ? 1 : surface.tailSide === "right" ? -1 : 0
            var inwardY = surface.tailSide === "top" ? 1 : surface.tailSide === "bottom" ? -1 : 0
            ctx.beginPath()
            ctx.moveTo(b.x - dx + inwardX, b.y - dy + inwardY)
            ctx.lineTo(t.x, t.y)
            ctx.lineTo(b.x + dx + inwardX, b.y + dy + inwardY)
            ctx.closePath(); ctx.fillStyle = surface.paperColor; ctx.fill()
            ctx.beginPath(); ctx.moveTo(b.x - dx, b.y - dy); ctx.lineTo(t.x, t.y)
            ctx.lineTo(b.x + dx, b.y + dy)
            ctx.strokeStyle = surface.edgeColor; ctx.lineWidth = 1; ctx.stroke()
        }
    }
}
