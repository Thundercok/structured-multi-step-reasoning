import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: finderResults
    objectName: "finderResults"
    visible: desk.liveSnapshot.view === "finder" && (desk.allFinderHits || []).length > 0
    Layout.fillWidth: true
    spacing: 6

    function scrollSelectionIntoView(index) {
        var item = finderRepeater.itemAt(index)
        var flick = finderListScroll.contentItem
        if (!item || !flick || finderListScroll.contentHeight <= finderListScroll.height) return
        var maxY = Math.max(0, finderListScroll.contentHeight - finderListScroll.height)
        if (item.y < flick.contentY)
            flick.contentY = Math.max(0, Math.min(maxY, item.y))
        else if (item.y + item.height > flick.contentY + finderListScroll.height)
            flick.contentY = Math.min(maxY, item.y + item.height - finderListScroll.height)
    }

    ScrollView {
        id: finderListScroll
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(finderListColumn.implicitHeight, 206)
        contentWidth: availableWidth
        contentHeight: finderListColumn.implicitHeight
        clip: true
        ColumnLayout {
            id: finderListColumn
            // Reserve a stable gutter. Toggling it from contentHeight feeds
            // wrapped text height back into the width during list collapse.
            width: Math.max(0, finderListScroll.availableWidth - 10)
            spacing: 4

            Repeater {
                id: finderRepeater
                model: desk.visibleFinderHits
                ColumnLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    spacing: 4

                    // Section header when category changes
                    Label {
                        visible: Boolean(modelData.is_first_of_section)
                            && (desk.allFinderHits || []).some(function(hit) { return hit.kind !== modelData.kind })
                        text: modelData.kind === "application" ? "Ứng dụng" : "Tài liệu & tệp"
                        color: desk.muted
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        Layout.topMargin: index === 0 ? 0 : 8
                        Layout.bottomMargin: 2
                    }

                    Rectangle {
                        id: hitCard
                        objectName: "finderHit_" + index
                        Layout.fillWidth: true
                        implicitHeight: hitRow.implicitHeight + 14
                        radius: desk.cardRadius
                        readonly property bool isSelected: desk.selectedFinderIndex === index
                        color: hitCard.isSelected ? desk.selectedSurface : (hitMouseArea.containsMouse ? desk.hoverSurface : "transparent")
                        border.color: hitCard.isSelected ? desk.selectedEdge : (hitMouseArea.containsMouse ? desk.edge : "transparent")
                        border.width: hitCard.isSelected ? 1.5 : 1
                        Accessible.name: modelData.title + ", " + (modelData.kind === "application" ? "Ứng dụng" : (modelData.is_pdf ? "PDF" : "Tệp")) + " tại " + (modelData.display_path || modelData.path) + ". Chọn để mở"

                        MouseArea {
                            id: hitMouseArea
                            anchors.fill: parent
                            z: 0
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                desk.selectedFinderIndex = index
                                editor.forceActiveFocus()
                            }
                            onDoubleClicked: {
                                desk.liveController.openSelectedHit(index)
                            }
                        }

                        Rectangle {
                            id: selectionAccentBar
                            visible: hitCard.isSelected
                            width: 3
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.margins: 4
                            radius: 1.5
                            color: desk.accent
                            z: 2
                        }

                        RowLayout {
                            id: hitRow
                            z: 1
                            anchors.fill: parent
                            anchors.topMargin: 7
                            anchors.bottomMargin: 7
                            anchors.leftMargin: hitCard.isSelected ? 13 : 10
                            anchors.rightMargin: 10
                            spacing: 10

                            Item {
                                Layout.preferredWidth: 28
                                Layout.preferredHeight: 28
                                Layout.alignment: Qt.AlignVCenter
                                Image {
                                    anchors.centerIn: parent
                                    visible: modelData.kind === "application"
                                    width: 28; height: 28
                                    source: visible && modelData.path ? "image://icon/" + modelData.path : ""
                                    sourceSize.width: 56; sourceSize.height: 56
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    visible: modelData.kind !== "application"
                                    radius: 7
                                    color: hitCard.isSelected ? desk.paperColor : desk.utilitySurface
                                    border.width: 1
                                    border.color: desk.edge
                                    DeskIcon {
                                        anchors.centerIn: parent
                                        name: modelData.is_pdf ? "pdf" : "file"
                                        color: modelData.is_pdf ? desk.pdfInk : desk.muted
                                        width: 17; height: 17
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 2

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Label {
                                        objectName: "finderTitle_" + index
                                        text: modelData.title
                                        textFormat: Text.PlainText
                                        color: desk.ink
                                        font.pixelSize: 13
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    Rectangle {
                                        id: kindBadge
                                        radius: 4
                                        color: desk.backingColor
                                        implicitHeight: 18
                                        implicitWidth: kindText.implicitWidth + 10
                                        Layout.alignment: Qt.AlignVCenter
                                        Label {
                                            id: kindText
                                            anchors.centerIn: parent
                                            text: modelData.kind === "application" ? "Ứng dụng" : (modelData.is_pdf ? "PDF" : "Tệp")
                                            textFormat: Text.PlainText
                                            color: desk.muted
                                            font.pixelSize: 10
                                            font.weight: Font.Medium
                                        }
                                    }
                                }

                                Label {
                                    objectName: "finderMatchReason_" + index
                                    text: (modelData.match_reason ? modelData.match_reason + " · " : "") + (modelData.display_path || modelData.path || modelData.snippet || "")
                                    textFormat: Text.PlainText
                                    color: desk.muted
                                    font.pixelSize: 11
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    ToolTip.visible: hitMouseArea.containsMouse
                                    ToolTip.text: modelData.path || ""
                                }
                                Label {
                                    objectName: "finderContentExcerpt_" + index
                                    visible: modelData.kind === "file" && Boolean(modelData.snippet)
                                    text: "Trích từ chỉ mục · " + (modelData.snippet || "")
                                    textFormat: Text.PlainText
                                    color: desk.ink
                                    font.pixelSize: 11
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Affordance to see more if there are remaining results
    Item {
        visible: desk.allFinderHits.length > 3
        Layout.fillWidth: true
        implicitHeight: seeMoreRow.implicitHeight + 8

        RowLayout {
            id: seeMoreRow
            anchors.centerIn: parent
            spacing: 6

            QuietButton {
                id: seeMoreButton
                objectName: "seeMoreFinderHits"
                text: desk.showAllFinderHits
                    ? "Thu gọn (hiện 3 gợi ý đầu)"
                    : ("Xem thêm " + desk.remainingFinderHits + " kết quả khác…")
                iconName: desk.showAllFinderHits ? "chevron-up" : "chevron-down"
                Accessible.name: desk.showAllFinderHits
                    ? "Thu gọn danh sách gợi ý còn 3 mục"
                    : ("Xem thêm " + desk.remainingFinderHits + " kết quả tìm kiếm còn lại")
                onClicked: {
                    if (desk.showAllFinderHits && finderListScroll.contentItem)
                        finderListScroll.contentItem.contentY = 0
                    desk.showAllFinderHits = !desk.showAllFinderHits
                    if (desk.selectedFinderIndex >= (desk.visibleFinderHits || []).length) {
                        desk.selectedFinderIndex = -1
                    }
                    editor.forceActiveFocus()
                }
            }
        }
    }

    // Bottom Action Bar reflecting selected hit actions cleanly with tactile keycaps
    Rectangle {
        visible: desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        Layout.fillWidth: true
        Layout.topMargin: 2
        height: 1
        color: desk.edge
    }
    Rectangle {
        id: bottomActionBar
        objectName: "bottomActionBar"
        visible: desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        Layout.fillWidth: true
        implicitHeight: finderShortcuts.implicitHeight + 10
        radius: desk.controlRadius
        color: "transparent"

        readonly property var selectedHit: (desk.visibleFinderHits || [])[desk.selectedFinderIndex] || ({})

        Flow {
            id: finderShortcuts
            x: 0
            y: 4
            width: parent.width
            spacing: 5

            KeycapBadge {
                objectName: "finderAdoptAction"
                visible: !desk.miniMode && (Boolean(bottomActionBar.selectedHit.is_pdf) || bottomActionBar.selectedHit.kind === "file")
                keyText: "Tab"
                labelText: bottomActionBar.width < 400 ? "Hỏi Chuột" : "Đưa vào bàn & Hỏi Chuột"
                primary: true
                onClicked: {
                    var idx = desk.selectedFinderIndex
                    desk.selectedFinderIndex = -1
                    desk.liveController.adoptSelectedHit(idx, editor.text)
                    editor.forceActiveFocus()
                }
            }
            KeycapBadge {
                objectName: "finderReadAction"
                visible: Boolean(bottomActionBar.selectedHit.is_pdf)
                keyText: "↵"
                labelText: desk.miniMode ? "Mở PDF" : bottomActionBar.width < 400 ? "Chọn PDF" : "Chọn PDF để đọc / hỏi"
                Accessible.name: "Chọn PDF để đọc hoặc hỏi Chuột, Enter"
                onClicked: {
                    var idx = desk.selectedFinderIndex
                    desk.selectedFinderIndex = -1
                    desk.liveController.openSelectedHit(idx)
                    editor.forceActiveFocus()
                }
            }
            KeycapBadge {
                visible: bottomActionBar.selectedHit.kind === "application"
                keyText: "↵"
                labelText: bottomActionBar.width < 400 ? "Mở" : "Mở ứng dụng"
                primary: true
                onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex)
            }
            KeycapBadge {
                objectName: "finderOpenExternalAction"
                visible: Boolean(bottomActionBar.selectedHit.is_pdf)
                keyText: ""
                labelText: "Mở bằng ứng dụng"
                onClicked: desk.liveController.openHit(bottomActionBar.selectedHit.path)
            }
            KeycapBadge {
                visible: bottomActionBar.selectedHit.kind === "file" && !bottomActionBar.selectedHit.is_pdf
                keyText: "↵"
                labelText: bottomActionBar.width < 400 ? "Mở" : "Mở tệp"
                onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex)
            }
            KeycapBadge {
                visible: !desk.miniMode && bottomActionBar.selectedHit.kind === "file" && !bottomActionBar.selectedHit.is_pdf
                keyText: "⇧↵"
                labelText: bottomActionBar.width < 400 ? "Hỏi" : "Hỏi về tệp"
                primary: true
                onClicked: desk.liveController.askAboutSelectedHit(desk.selectedFinderIndex, editor.text)
            }
            KeycapBadge {
                visible: !desk.miniMode && Boolean(bottomActionBar.selectedHit.path)
                keyText: "⌘Y"
                labelText: "Xem nhanh"
                onClicked: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
            }
            KeycapBadge {
                visible: Boolean(bottomActionBar.selectedHit.path)
                keyText: "⌘↵"
                labelText: "Finder"
                onClicked: desk.liveController.revealSelectedInFinder(desk.selectedFinderIndex)
            }
        }
    }
}
