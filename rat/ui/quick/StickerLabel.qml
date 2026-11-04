import QtQuick
import QtQuick.Controls

// A small label stuck on slightly crooked, with a shadow where it lifts off the paper.
Item {
    id: sticker
    property string text: ""
    property color fillColor: desk.backingColor
    property color textColor: desk.ink
    property real tilt: -2
    implicitHeight: 18
    implicitWidth: stickerText.implicitWidth + 12
    rotation: tilt
    Accessible.name: text
    Rectangle {
        x: 1; y: 1
        width: parent.width; height: parent.height
        radius: 3
        antialiasing: true
        color: Qt.rgba(0, 0, 0, 0.16)
    }
    Rectangle {
        anchors.fill: parent
        radius: 3
        antialiasing: true
        color: sticker.fillColor
        Label {
            id: stickerText
            anchors.centerIn: parent
            text: sticker.text
            textFormat: Text.PlainText
            color: sticker.textColor
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }
    }
}
