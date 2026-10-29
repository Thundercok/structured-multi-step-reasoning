import QtQuick
import QtQuick.Controls

// Text + symbol conveys state without relying on a colored dot.
ToolButton {
    id: status
    property string label: "Sẵn sàng"
    property bool pending: false
    property bool busy: false
    property bool paused: false
    readonly property bool emphasized: pending || busy || paused || hovered || visualFocus
    property color paperColor: "#fdfefb"
    property color inkColor: "#2c302a"
    property color edgeColor: "#dce3d4"
    width: 112; height: 24
    Accessible.name: pending ? "Có đoạn Clipboard chờ. Bấm để xem trước." : label
    contentItem: Text {
        text: (status.pending ? "1  " : status.busy ? "…  " : status.paused ? "Ⅱ  " : "•  ") + status.label
        color: status.inkColor; font.pixelSize: 11
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: status.emphasized ? 12 : 6
        color: Qt.rgba(status.paperColor.r, status.paperColor.g, status.paperColor.b, status.emphasized ? 1 : 0.55)
        border.width: status.emphasized ? 1 : 0
        border.color: status.edgeColor
    }
    ToolTip.visible: hovered
    ToolTip.text: status.pending ? "Xem trước đoạn Clipboard; chưa dịch và vẫn giữ công việc hiện tại." : status.label
}
