import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property bool primary: false
    property bool elideText: false
    opacity: enabled ? 1 : 0.45
    hoverEnabled: true
    font.pixelSize: 12
    leftPadding: 9
    rightPadding: 9
    topPadding: 7
    bottomPadding: 7
    property string iconName: ""
    property string trailingIconName: ""
    property int iconSize: 16
    property int trailingIconSize: 13
    property color iconColor: "transparent"
    contentItem: RowLayout {
        property color color: control.primary ? desk.accentText : control.highlighted ? desk.accent : desk.muted
        spacing: (control.iconName || control.trailingIconName) && control.text ? 5 : 0
        DeskIcon {
            visible: Boolean(control.iconName)
            name: control.iconName
            color: control.iconColor.a > 0 ? control.iconColor : parent.color
            width: control.iconSize
            height: control.iconSize
            Layout.preferredWidth: control.iconSize
            Layout.preferredHeight: control.iconSize
            Layout.alignment: control.text ? Qt.AlignVCenter : (Qt.AlignHCenter | Qt.AlignVCenter)
        }
        Text {
            visible: Boolean(control.text)
            Layout.fillWidth: true
            text: control.text
            color: parent.color
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: control.elideText ? Text.NoWrap : Text.Wrap
            elide: control.elideText ? Text.ElideMiddle : Text.ElideNone
        }
        DeskIcon {
            visible: Boolean(control.trailingIconName)
            name: control.trailingIconName
            color: parent.color
            width: control.trailingIconSize
            height: control.trailingIconSize
            Layout.preferredWidth: control.trailingIconSize
            Layout.preferredHeight: control.trailingIconSize
            Layout.alignment: Qt.AlignVCenter
        }
    }
    background: Rectangle {
        radius: desk.controlRadius
        color: control.primary
            ? (control.down ? Qt.darker(desk.accent, 1.12) : control.hovered ? Qt.darker(desk.accent, 1.05) : desk.accent)
            : (control.down || control.highlighted ? desk.selectedSurface : control.hovered ? desk.hoverSurface : "transparent")
        border.color: desk.accent
        border.width: control.visualFocus ? 2 : 0
    }
}
