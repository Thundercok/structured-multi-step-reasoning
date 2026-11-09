import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: cardRoot
    property var cardData: ({})
    readonly property string visualType: cardData ? (cardData.visual_type || "") : ""

    visible: visualType !== ""
    implicitHeight: contentCol.implicitHeight + 24
    radius: 12
    color: desk.utilitySurface
    border.width: 1
    border.color: desk.edge

    ColumnLayout {
        id: contentCol
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // --- 1. KINH DỊCH (I CHING) ---
        ColumnLayout {
            visible: cardRoot.visualType === "iching"
            Layout.fillWidth: true
            spacing: 10

            // Header Tag
            RowLayout {
                spacing: 8
                Rectangle {
                    radius: 5
                    color: Qt.rgba(desk.accent.r, desk.accent.g, desk.accent.b, 0.15)
                    border.width: 1
                    border.color: desk.selectedEdge
                    implicitWidth: ichingTag.implicitWidth + 12
                    implicitHeight: 22
                    Label {
                        id: ichingTag
                        anchors.centerIn: parent
                        text: "🔮 QUẺ KINH DỊCH"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: desk.accent
                    }
                }
                Label {
                    text: cardRoot.cardData ? (cardRoot.cardData.question || "") : ""
                    font.pixelSize: 12
                    color: desk.muted
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            // Hexagram Visual + Description Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                // 6 Yin/Yang Lines (Drawn from Line 6 down to Line 1)
                Rectangle {
                    implicitWidth: 120
                    implicitHeight: 88
                    radius: 8
                    color: desk.inputColor
                    border.width: 1
                    border.color: desk.edge

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 5
                        Repeater {
                            // lines array is 0..5 (line 1 is index 0, line 6 is index 5).
                            // Display top to bottom: index 5 down to 0.
                            model: 6
                            Item {
                                readonly property int lineNum: 6 - index // 6, 5, 4, 3, 2, 1
                                readonly property int lineIdx: lineNum - 1
                                readonly property var rawLines: cardRoot.cardData && cardRoot.cardData.lines ? cardRoot.cardData.lines : [1,1,1,1,1,1]
                                readonly property int isYang: lineIdx < rawLines.length ? rawLines[lineIdx] : 1
                                readonly property var changingList: cardRoot.cardData && cardRoot.cardData.changing_lines ? cardRoot.cardData.changing_lines : []
                                readonly property bool isChanging: changingList.indexOf(lineNum) !== -1

                                implicitWidth: 92
                                implicitHeight: 7

                                RowLayout {
                                    anchors.centerIn: parent
                                    spacing: 8
                                    visible: isYang === 0 // Yin (2 broken bars)
                                    Rectangle {
                                        width: 40; height: 6; radius: 3
                                        color: isChanging ? desk.warningInk : desk.accent
                                    }
                                    Rectangle {
                                        width: 40; height: 6; radius: 3
                                        color: isChanging ? desk.warningInk : desk.accent
                                    }
                                }
                                Rectangle {
                                    anchors.centerIn: parent
                                    visible: isYang === 1 // Yang (1 solid bar)
                                    width: 88; height: 6; radius: 3
                                    color: isChanging ? desk.warningInk : desk.accent
                                }
                            }
                        }
                    }
                }

                // Hexagram Details
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Label {
                        text: cardRoot.cardData ? (cardRoot.cardData.hexagram_name || "") : ""
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: desk.ink
                    }
                    Label {
                        text: cardRoot.cardData ? ("Thượng: " + (cardRoot.cardData.upper_trigram || "") + " · Hạ: " + (cardRoot.cardData.lower_trigram || "")) : ""
                        font.pixelSize: 11
                        color: desk.muted
                    }
                    Label {
                        text: cardRoot.cardData ? (cardRoot.cardData.meaning || "") : ""
                        font.pixelSize: 12
                        color: desk.ink
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }

            // Chuột's Advice Pill
            Rectangle {
                visible: Boolean(cardRoot.cardData && cardRoot.cardData.advice)
                Layout.fillWidth: true
                radius: 8
                color: desk.inputColor
                border.width: 1
                border.color: desk.edge
                implicitHeight: adviceText.implicitHeight + 14

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8
                    Label { text: "💡"; font.pixelSize: 14 }
                    Label {
                        id: adviceText
                        text: cardRoot.cardData ? (cardRoot.cardData.advice || "") : ""
                        font.pixelSize: 12
                        color: desk.ink
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }
        }

        // --- 2. LENORMAND ORACLE (3 CARDS) ---
        ColumnLayout {
            visible: cardRoot.visualType === "lenormand"
            Layout.fillWidth: true
            spacing: 10

            // Header Tag
            RowLayout {
                spacing: 8
                Rectangle {
                    radius: 5
                    color: Qt.rgba(desk.accent.r, desk.accent.g, desk.accent.b, 0.15)
                    border.width: 1
                    border.color: desk.selectedEdge
                    implicitWidth: lenTag.implicitWidth + 12
                    implicitHeight: 22
                    Label {
                        id: lenTag
                        anchors.centerIn: parent
                        text: "🃏 BÀI LENORMAND"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: desk.accent
                    }
                }
                Label {
                    text: cardRoot.cardData ? (cardRoot.cardData.question || "Trải bài 3 lá") : ""
                    font.pixelSize: 12
                    color: desk.muted
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            // 3 Card Spread Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Repeater {
                    model: cardRoot.cardData && cardRoot.cardData.cards ? cardRoot.cardData.cards : []
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        implicitHeight: 124
                        radius: 8
                        color: desk.inputColor
                        border.width: 1
                        border.color: desk.edge

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 3

                            // Slot Label (Past/Present/Future)
                            Label {
                                text: (modelData.slot || "").toUpperCase()
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                color: desk.muted
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            // Card Emoji Icon
                            Label {
                                text: modelData.icon || "🎴"
                                font.pixelSize: 26
                                Layout.alignment: Qt.AlignHCenter
                            }

                            // Card Name
                            Label {
                                text: modelData.name || ""
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: desk.ink
                                elide: Text.ElideRight
                                Layout.alignment: Qt.AlignHCenter
                            }

                            // Meaning
                            Label {
                                text: modelData.meaning || ""
                                font.pixelSize: 10
                                color: desk.muted
                                wrapMode: Text.Wrap
                                elide: Text.ElideRight
                                maximumLineCount: 2
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        // --- 3. THỜI KHÓA BIỂU (TIMETABLE) ---
        ColumnLayout {
            visible: cardRoot.visualType === "timetable"
            Layout.fillWidth: true
            spacing: 10

            // Header Tag
            RowLayout {
                spacing: 8
                Rectangle {
                    radius: 5
                    color: Qt.rgba(desk.accent.r, desk.accent.g, desk.accent.b, 0.15)
                    border.width: 1
                    border.color: desk.selectedEdge
                    implicitWidth: ttTag.implicitWidth + 12
                    implicitHeight: 22
                    Label {
                        id: ttTag
                        anchors.centerIn: parent
                        text: "📅 THỜI KHÓA BIỂU"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: desk.accent
                    }
                }
                Label {
                    text: cardRoot.cardData ? (cardRoot.cardData.day || "Hôm nay") : ""
                    font.pixelSize: 12
                    font.weight: Font.Medium
                    color: desk.ink
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: cardRoot.cardData && cardRoot.cardData.sessions ? (cardRoot.cardData.sessions.length + " môn học") : ""
                    font.pixelSize: 11
                    color: desk.muted
                }
            }

            // Sessions List
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Repeater {
                    model: cardRoot.cardData && cardRoot.cardData.sessions ? cardRoot.cardData.sessions : []
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 46
                        radius: 8
                        color: desk.inputColor
                        border.width: 1
                        border.color: desk.edge

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10

                            // Time Badge
                            Rectangle {
                                radius: 4
                                color: desk.accent
                                implicitWidth: timeLbl.implicitWidth + 10
                                implicitHeight: 22
                                Label {
                                    id: timeLbl
                                    anchors.centerIn: parent
                                    text: modelData.time || ""
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    color: desk.accentText
                                }
                            }

                            // Room Badge
                            Rectangle {
                                radius: 4
                                color: desk.selectedSurface
                                border.width: 1
                                border.color: desk.selectedEdge
                                implicitWidth: roomLbl.implicitWidth + 10
                                implicitHeight: 22
                                Label {
                                    id: roomLbl
                                    anchors.centerIn: parent
                                    text: modelData.room ? ("Phòng " + modelData.room) : "Chưa rõ phòng"
                                    font.pixelSize: 10
                                    color: desk.ink
                                }
                            }

                            // Course Name & Instructor
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Label {
                                    text: modelData.course_name || ""
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: desk.ink
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Label {
                                    text: modelData.instructor ? ("GV: " + modelData.instructor) : ""
                                    font.pixelSize: 10
                                    color: desk.muted
                                    visible: Boolean(modelData.instructor)
                                }
                            }
                        }
                    }
                }

                Label {
                    visible: cardRoot.cardData && (!cardRoot.cardData.sessions || cardRoot.cardData.sessions.length === 0)
                    text: "🎉 Không có tiết học nào trong ngày này. Bạn được nghỉ!"
                    font.pixelSize: 12
                    color: desk.muted
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        // --- 4. WEB READER SUMMARY ---
        ColumnLayout {
            visible: cardRoot.visualType === "web"
            Layout.fillWidth: true
            spacing: 8

            // Header Tag
            RowLayout {
                spacing: 8
                Rectangle {
                    radius: 5
                    color: Qt.rgba(desk.accent.r, desk.accent.g, desk.accent.b, 0.15)
                    border.width: 1
                    border.color: desk.selectedEdge
                    implicitWidth: webTag.implicitWidth + 12
                    implicitHeight: 22
                    Label {
                        id: webTag
                        anchors.centerIn: parent
                        text: "🌐 TRANG WEB"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: desk.accent
                    }
                }
                Rectangle {
                    visible: Boolean(cardRoot.cardData && cardRoot.cardData.domain)
                    radius: 4
                    color: desk.selectedSurface
                    border.width: 1
                    border.color: desk.selectedEdge
                    implicitWidth: domLbl.implicitWidth + 8
                    implicitHeight: 20
                    Label {
                        id: domLbl
                        anchors.centerIn: parent
                        text: cardRoot.cardData ? (cardRoot.cardData.domain || "") : ""
                        font.pixelSize: 10
                        color: desk.accent
                    }
                }
                Item { Layout.fillWidth: true }
                QuietButton {
                    text: "Mở web"
                    plain: true
                    font.pixelSize: 11
                    visible: Boolean(cardRoot.cardData && cardRoot.cardData.url)
                    onClicked: {
                        if (cardRoot.cardData && cardRoot.cardData.url) {
                            Qt.openUrlExternally(cardRoot.cardData.url)
                        }
                    }
                }
            }

            // Title
            Label {
                text: cardRoot.cardData ? (cardRoot.cardData.title || "") : ""
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: desk.ink
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            // Bullets
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 5
                Repeater {
                    model: cardRoot.cardData && cardRoot.cardData.bullets ? cardRoot.cardData.bullets : []
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Label {
                            text: "•"
                            font.pixelSize: 14
                            color: desk.accent
                            Layout.alignment: Qt.AlignTop
                        }
                        Label {
                            text: modelData
                            font.pixelSize: 12
                            color: desk.ink
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
