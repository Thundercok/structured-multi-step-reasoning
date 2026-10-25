import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: appsResults
    objectName: "appsResults"
    property alias appsRepeaterItem: appsRepeater
    Layout.fillWidth: true
    spacing: 12

    // State 3: Empty State (when filter matches no app)
    Rectangle {
        id: appsEmptyCard
        objectName: "appsEmptyCard"
        visible: desk.filteredApps.length === 0
        Layout.fillWidth: true
        implicitHeight: emptyColumn.implicitHeight + 32
        radius: desk.cardRadius
        color: desk.utilitySurface
        border.color: desk.edge

        ColumnLayout {
            id: emptyColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 16
            spacing: 8

            DeskIcon {
                name: "search"
                color: desk.muted
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
            }

            Label {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                text: "Không tìm thấy ứng dụng khớp với \"" + (editor.text || "").trim() + "\""
                color: desk.ink
                font.pixelSize: 13
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Label {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                text: "Thử tìm theo tên tiếng Anh, alias hoặc xóa bộ lọc."
                color: desk.muted
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 10
                Layout.topMargin: 4

                QuietButton {
                    objectName: "clearAppsFilter"
                    text: "Xóa bộ lọc"
                    primary: true
                    onClicked: {
                        editor.text = ""
                        editor.forceActiveFocus()
                    }
                }
                QuietButton {
                    objectName: "exitAppsView"
                    text: "Về Bàn làm việc"
                    onClicked: {
                        var restored = desk.liveController.closeAppsView()
                        editor.text = restored
                        editor.forceActiveFocus()
                    }
                }
            }
        }
    }

    // State 1 & State 2: Grid View (Unfiltered & Filtered)
    Flow {
        id: appsGridFlow
        objectName: "appsGridFlow"
        visible: desk.filteredApps.length > 0
        Layout.fillWidth: true
        spacing: 10

        readonly property int cardWidth: Math.max(90, Math.floor((resultScroll.availableWidth - 10 * (desk.gridColumns - 1)) / desk.gridColumns))

        Repeater {
            id: appsRepeater
            model: desk.filteredApps

            Rectangle {
                id: appCell
                objectName: "appCard_" + index
                width: appsGridFlow.cardWidth
                height: 112
                radius: desk.cardRadius
                readonly property bool isSelected: desk.selectedAppGridIndex === index
                readonly property bool isHovered: cellMouse.containsMouse
                color: isSelected
                    ? desk.selectedSurface
                    : (isHovered
                        ? desk.hoverSurface
                        : (desk.darkMode ? Qt.rgba(1, 1, 1, 0.03) : Qt.rgba(0, 0, 0, 0.02)))
                border.color: isSelected
                    ? desk.selectedEdge
                    : "transparent"
                border.width: 1

                MouseArea {
                    id: cellMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: desk.selectedAppGridIndex = index
                    onClicked: {
                        desk.liveController.launchApplication(modelData.path)
                        var restored = desk.liveController.closeAppsView()
                        editor.text = restored
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 6
                    anchors.topMargin: 8
                    anchors.bottomMargin: 6
                    spacing: 5

                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 52
                        Layout.preferredHeight: 52
                        Layout.minimumWidth: 52
                        Layout.minimumHeight: 52
                        Layout.maximumWidth: 52
                        Layout.maximumHeight: 52
                        width: 52
                        height: 52
                        source: modelData.icon_url || ("image://icon/" + modelData.path)
                        sourceSize.width: 104
                        sourceSize.height: 104
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
                        text: modelData.name || ""
                        color: desk.ink
                        font.pixelSize: 12
                        font.weight: Font.Normal
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignTop
                        elide: Text.ElideRight
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        lineHeight: 1.15
                    }
                }
            }
        }
    }

    // Bottom Action Bar for selected app in grid
    Rectangle {
        id: appsBottomBar
        objectName: "appsBottomBar"
        visible: desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length
        Layout.fillWidth: true
        implicitHeight: appShortcuts.implicitHeight + 12
        radius: desk.controlRadius
        color: "transparent"

        readonly property var currentApp: desk.filteredApps[desk.selectedAppGridIndex] || ({})

        Flow {
            id: appShortcuts
            x: 0
            y: 6
            width: parent.width
            spacing: appsBottomBar.width < 400 ? 6 : 8

            Label {
                id: bottomBarAppName
                text: appsBottomBar.currentApp.name || ""
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: desk.ink
                elide: Text.ElideRight
                width: Math.max(90, Math.min(160, appsBottomBar.width * 0.25))
                height: 20
                verticalAlignment: Text.AlignVCenter
            }

            Label {
                id: bottomBarAppPath
                text: appsBottomBar.currentApp.path || ""
                font.pixelSize: 10
                color: desk.muted
                elide: Text.ElideMiddle
                width: Math.max(0, appShortcuts.width - bottomBarAppName.width - 290)
                visible: width >= 40
                height: 20
                verticalAlignment: Text.AlignVCenter
                Layout.minimumWidth: 0
                opacity: 0.75
            }

            KeycapBadge {
                objectName: "appOpenAction"
                keyText: "↵"
                labelText: appsBottomBar.width < 400 ? "Mở" : "Mở ứng dụng"
                Accessible.name: "Mở ứng dụng đã chọn, Enter"
                primary: true
                Layout.alignment: Qt.AlignVCenter
                onClicked: {
                    desk.liveController.launchApplication(appsBottomBar.currentApp.path)
                    var restored = desk.liveController.closeAppsView()
                    editor.text = restored
                }
            }

            KeycapBadge {
                keyText: "⌘↵"
                labelText: "Finder"
                Layout.alignment: Qt.AlignVCenter
                onClicked: {
                    desk.liveController.revealInFinder(appsBottomBar.currentApp.path)
                }
            }

            KeycapBadge {
                keyText: "Esc"
                labelText: "Quay lại"
                Layout.alignment: Qt.AlignVCenter
                onClicked: {
                    var restored = desk.liveController.closeAppsView()
                    editor.text = restored
                    editor.forceActiveFocus()
                }
            }
        }
    }
}
