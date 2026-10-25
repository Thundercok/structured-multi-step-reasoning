import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: keycapRoot
    property string keyText: ""
    property string labelText: ""
    property bool primary: false
    text: labelText
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: labelText + ", " + keyText
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    implicitHeight: 26
    leftPadding: 6
    rightPadding: 6
    topPadding: 3
    bottomPadding: 3
    Layout.alignment: Qt.AlignVCenter
    opacity: enabled ? 1 : 0.45

    contentItem: RowLayout {
        spacing: 5
        Label {
            text: keycapRoot.labelText
            color: keycapRoot.primary ? desk.accent : desk.muted
            font.pixelSize: 11
            font.weight: keycapRoot.primary ? Font.Medium : Font.Normal
        }
        Rectangle {
            visible: keycapRoot.keyText.length > 0
            radius: 4
            color: keycapRoot.primary ? Qt.rgba(0.31, 0.40, 0.25, 0.10) : desk.utilitySurface
            border.width: 1
            border.color: desk.edge
            implicitWidth: keyGlyph.implicitWidth + 6
            implicitHeight: 16
            Label {
                id: keyGlyph
                anchors.centerIn: parent
                text: keycapRoot.keyText
                color: keycapRoot.primary ? desk.accent : desk.muted
                font.pixelSize: 10
            }
        }
    }
    background: Rectangle {
        radius: 6
        color: keycapRoot.down ? desk.backingColor
            : keycapRoot.primary ? desk.selectedSurface
            : keycapRoot.hovered ? desk.hoverSurface : "transparent"
        border.color: desk.accent
        border.width: keycapRoot.visualFocus ? 2 : 0
    }
}
