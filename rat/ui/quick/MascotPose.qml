import QtQuick

// Optical sizing and speech anchor metadata; no mode or business logic.
Item {
    id: pose
    property url source
    property rect inkBounds: Qt.rect(0.08, 0.06, 0.84, 0.88)
    property point mouth: Qt.point(0.35, 0.48)
    property real opticalHeight: 70
    property real bottomPadding: 6
    readonly property real aspectRatio: sprite.sourceSize.height > 0 ? sprite.sourceSize.width / sprite.sourceSize.height : 1
    readonly property rect visualBounds: Qt.rect(sprite.x + inkBounds.x * sprite.width,
        sprite.y + inkBounds.y * sprite.height, inkBounds.width * sprite.width, inkBounds.height * sprite.height)
    readonly property point speechAnchor: Qt.point(sprite.x + mouth.x * sprite.width, sprite.y + mouth.y * sprite.height)
    Image {
        id: sprite
        source: pose.source
        height: Math.min(pose.opticalHeight / Math.max(0.01, pose.inkBounds.height),
            Math.max(1, pose.width - 4) / Math.max(0.01, pose.inkBounds.width * pose.aspectRatio),
            Math.max(1, pose.height - pose.bottomPadding) / Math.max(0.01, pose.inkBounds.height))
        width: height * pose.aspectRatio
        x: pose.width / 2 - (pose.inkBounds.x + pose.inkBounds.width / 2) * width
        y: pose.height - pose.bottomPadding - (pose.inkBounds.y + pose.inkBounds.height) * height
        fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
        Accessible.ignored: true
    }
}
