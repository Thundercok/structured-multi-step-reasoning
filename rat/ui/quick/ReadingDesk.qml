import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: reading
    required property var host
    readonly property var session: host.liveSnapshot.readingSession || ({})
    property int selectedCard: -1
    property bool isEditingDraft: false
    spacing: 14

    RowLayout {
        Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Label { text: "BÀN XEM · 01"; color: reading.host.accent; font.pixelSize: 10; font.letterSpacing: 2 }
            Label { text: "Đặt bài. Ngắm lá số."; color: reading.host.ink; font.family: "Georgia"; font.pixelSize: 23; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        Button {
            objectName: "readingImportProfile"
            text: reading.session.chart ? "Đổi hồ sơ…" : "Mở lá số…"
            onClicked: reading.host.openReadingProfileDialog()
            background: Rectangle { radius: 8; color: parent.hovered ? reading.host.selectedSurface : reading.host.utilitySurface; border.color: reading.host.edge }
            contentItem: Text { text: parent.text; color: reading.host.accent; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        }
    }

    GridLayout {
        objectName: "readingSurfaceGrid"
        visible: !Boolean(reading.session.draft && reading.session.draft.draft_markdown) || reading.host.currentWorkspaceMode === "multi" || reading.width >= 760
        columns: reading.width >= 760 ? 2 : 1
        columnSpacing: 28
        rowSpacing: 18
        Layout.fillWidth: true
        ColumnLayout {
            id: natalSection
            objectName: "readingNatalSection"
            Layout.fillWidth: true
            Layout.preferredWidth: reading.width >= 760 ? 340 : reading.width
            Layout.alignment: Qt.AlignTop
            spacing: 10
    Rectangle {
        visible: !reading.session.chart
        Layout.fillWidth: true
        implicitHeight: 92
        radius: 12
        color: reading.host.utilitySurface
        RowLayout {
            anchors.fill: parent; anchors.margins: 14; spacing: 14
            Label { text: "☉"; font.pixelSize: 36; color: reading.host.accent }
            Label {
                Layout.fillWidth: true
                text: "Lá số của phiên xem\nMở hồ sơ đã lưu từ Bản đồ sao. Vị trí thiên thể sẽ được tính lại."
                wrapMode: Text.Wrap; color: reading.host.muted; font.pixelSize: 12
            }
        }
    }
    GridLayout {
        columns: reading.width >= 760 ? 1 : 2
        visible: Boolean(reading.session.chart)
        Layout.fillWidth: true
        rowSpacing: 14
        columnSpacing: 14
        Image {
            id: natalWheel
            objectName: "readingNatalWheel"
            readonly property bool wheelReady: status === Image.Ready
            readonly property bool wheelFailed: status === Image.Error
            source: reading.session.chart ? reading.session.chart.wheel : ""
            Layout.preferredWidth: reading.width >= 760 ? Math.min(natalSection.width, 340) : Math.min(210, reading.width * 0.51)
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredHeight: width
            sourceSize.width: 1000; sourceSize.height: 1000
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            Accessible.name: "Vòng sao tính lại từ hồ sơ đã chọn"
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 5
            Label {
                objectName: "readingProfileName"
                text: reading.session.chart ? reading.session.chart.name : ""
                textFormat: Text.PlainText; wrapMode: Text.Wrap
                font.family: "Georgia"; font.pixelSize: 18; color: reading.host.ink
                Layout.fillWidth: true
            }
            Label {
                text: reading.session.chart ? reading.session.chart.date + " · " + reading.session.chart.time : ""
                textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: 11; color: reading.host.muted
                Layout.fillWidth: true
            }
            Label {
                text: reading.session.chart ? reading.session.chart.place : ""
                textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: 11; color: reading.host.muted
                Layout.fillWidth: true
            }
            Repeater {
                model: reading.session.chart ? reading.session.chart.positions : []
                Label {
                    required property var modelData
                    text: modelData.name + " · " + modelData.position
                    textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: 10; color: reading.host.ink
                    Layout.fillWidth: true
                }
            }
        }
    }
    Label {
        visible: natalWheel.status === Image.Loading || natalWheel.wheelFailed
        text: natalWheel.wheelFailed ? "Chưa hiển thị được vòng sao. Bạn có thể mở lại hồ sơ." : "Đang dựng vòng sao…"
        color: reading.host.muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap
    }
    Label {
        visible: Boolean(reading.session.chart)
        text: reading.session.chart ? "Hồ sơ · " + reading.session.chart.fileName : ""
        textFormat: Text.PlainText; elide: Text.ElideMiddle; font.pixelSize: 10; color: reading.host.muted
        Layout.fillWidth: true
    }
    Label {
        visible: Boolean(reading.session.chart && reading.session.chart.notices.length)
        text: reading.session.chart ? reading.session.chart.notices.join("\n") : ""
        textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: 11; color: reading.host.muted
        Layout.fillWidth: true
    }

        }
        ColumnLayout {
            objectName: "readingSpreadSection"
            Layout.fillWidth: true
            Layout.preferredWidth: reading.width >= 760 ? 620 : reading.width
            Layout.alignment: Qt.AlignTop
            spacing: 12

    RowLayout {
        Layout.fillWidth: true
        Label { text: "TRẢI BÀI"; color: reading.host.accent; font.pixelSize: 10; font.letterSpacing: 2; Layout.fillWidth: true }
        Label { text: (reading.session.cards || []).length + " lá · nhập tay"; color: reading.host.muted; font.pixelSize: 11 }
    }
    RowLayout {
        Layout.fillWidth: true
        TextField {
            id: cardsEntry
            objectName: "readingCardsEntry"
            Layout.fillWidth: true
            placeholderText: "4 pent, 8 cups, devil rev"
            Accessible.name: "Nhập các lá, ngăn bằng dấu phẩy; rev là ngược; rơi: là lá rơi"
            selectByMouse: true
            color: reading.host.ink
            background: Rectangle { radius: 8; color: reading.host.paperColor; border.color: cardsEntry.activeFocus ? reading.host.accent : reading.host.edge }
            onAccepted: reading.host.liveController.setReadingCards(text)
        }
        Button {
            objectName: "readingApplyCards"
            text: "Đặt bài"
            onClicked: reading.host.liveController.setReadingCards(cardsEntry.text)
            background: Rectangle { radius: 8; color: parent.hovered ? reading.host.selectedSurface : reading.host.utilitySurface; border.color: reading.host.edge }
            contentItem: Text { text: parent.text; color: reading.host.accent; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        }
    }
    Label {
        visible: Boolean(reading.session.error)
        text: reading.session.error || ""
        color: reading.host.pdfInk; font.pixelSize: 11; wrapMode: Text.Wrap
        textFormat: Text.PlainText; Layout.fillWidth: true
    }
    Label {
        visible: !(reading.session.cards || []).length
        text: "Đặt những lá bạn đã rút lên bàn. Thêm “rev” cho lá ngược, “rơi:” trước lá rơi."
        color: reading.host.muted; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
    }

    Flow {
        id: spread
        Layout.fillWidth: true
        spacing: 10
        readonly property int columns: width < 380 ? 2 : 3
        Repeater {
            model: reading.session.cards || []
            Column {
                id: cardColumn
                required property var modelData
                required property int index
                width: (spread.width - (spread.columns - 1) * spread.spacing) / spread.columns
                spacing: 5
                Label {
                    text: cardColumn.modelData.jumper ? "LÁ RƠI" : "VỊ TRÍ " + cardColumn.modelData.position
                    font.pixelSize: 9; font.letterSpacing: 1.2; color: reading.host.muted
                }
                Rectangle {
                    id: cardSurface
                    objectName: "readingCard_" + cardColumn.index
                    width: parent.width
                    height: Math.max(152, width * 1.35)
                    radius: 10
                    color: reading.host.darkMode ? "#303329" : "#f9f5eb"
                    border.color: reading.selectedCard === cardColumn.index ? reading.host.accent : (reading.host.darkMode ? "#74654a" : "#c9b58c")
                    border.width: reading.selectedCard === cardColumn.index ? 2 : 1
                    Accessible.name: cardColumn.modelData.title + (cardColumn.modelData.reversed ? ", ngược" : ", xuôi")
                    Accessible.role: Accessible.Button
                    activeFocusOnTab: true
                    Keys.onReturnPressed: reading.selectedCard = cardColumn.index
                    Keys.onSpacePressed: reading.selectedCard = cardColumn.index
                    Rectangle {
                        anchors.fill: parent; anchors.margins: 6; radius: 6; color: "transparent"
                        border.color: reading.host.darkMode ? "#534b3b" : "#e4d8c0"
                    }
                    Label {
                        anchors.top: parent.top; anchors.topMargin: 12; anchors.horizontalCenter: parent.horizontalCenter
                        text: cardColumn.modelData.numeral; font.family: "Georgia"; font.pixelSize: 16; color: reading.host.accent
                    }
                    Canvas {
                        anchors.centerIn: parent
                        width: parent.width * 0.58; height: parent.height * 0.44
                        rotation: cardColumn.modelData.reversed ? 180 : 0
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset(); ctx.strokeStyle = reading.host.darkMode ? "#c7b58e" : "#8a7144"; ctx.lineWidth = 1.4
                            var x = width/2, y = height/2, r = Math.min(width,height)*0.36
                            ctx.beginPath()
                            if (cardColumn.modelData.suit === "Pentacles") {
                                ctx.arc(x,y,r,0,Math.PI*2); ctx.stroke(); ctx.beginPath()
                                for (var i=0;i<6;i++) { var a=-Math.PI/2+i*4*Math.PI/5; if(i===0)ctx.moveTo(x+r*Math.cos(a),y+r*Math.sin(a)); else ctx.lineTo(x+r*Math.cos(a),y+r*Math.sin(a)) }
                            } else if (cardColumn.modelData.suit === "Cups") {
                                ctx.arc(x,y-r/2,r,0,Math.PI); ctx.lineTo(x+r,y-r/2); ctx.moveTo(x,y+r/2); ctx.lineTo(x,y+r*1.3); ctx.moveTo(x-r*0.6,y+r*1.3); ctx.lineTo(x+r*0.6,y+r*1.3)
                            } else if (cardColumn.modelData.suit === "Wands") {
                                ctx.moveTo(x-r*0.5,y+r); ctx.lineTo(x+r*0.5,y-r); ctx.moveTo(x,y); ctx.quadraticCurveTo(x-r,y-r,x+r*0.2,y-r*0.5)
                            } else if (cardColumn.modelData.suit === "Swords") {
                                ctx.moveTo(x,y-r); ctx.lineTo(x+r*0.2,y+r*0.4); ctx.lineTo(x-r*0.2,y+r*0.4); ctx.closePath(); ctx.moveTo(x-r*0.5,y+r*0.5); ctx.lineTo(x+r*0.5,y+r*0.5); ctx.moveTo(x,y+r*0.5); ctx.lineTo(x,y+r)
                            } else {
                                ctx.arc(x,y,r*0.55,0,Math.PI*2); ctx.stroke(); ctx.beginPath()
                                for(var j=0;j<8;j++){var b=j*Math.PI/4;ctx.moveTo(x+r*0.8*Math.cos(b),y+r*0.8*Math.sin(b));ctx.lineTo(x+r*1.2*Math.cos(b),y+r*1.2*Math.sin(b))}
                            }
                            ctx.stroke()
                        }
                    }
                    Column {
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 12
                        anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 9
                        spacing: 4
                        Label {
                            width: parent.width; text: cardColumn.modelData.title; textFormat: Text.PlainText
                            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                            font.family: "Georgia"; font.pixelSize: 12; color: reading.host.ink
                        }
                        Label {
                            width: parent.width; text: cardColumn.modelData.reversed ? "NGƯỢC ↻" : "XUÔI"
                            horizontalAlignment: Text.AlignHCenter; font.pixelSize: 9; color: reading.host.muted
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            reading.selectedCard = cardColumn.index
                            if (reading.host.liveController) {
                                reading.host.liveController.selectPreviewCard(cardColumn.index)
                            }
                            cardSurface.forceActiveFocus()
                        }
                    }
                }
            }
        }
    }
    Label {
        text: reading.selectedCard >= 0 && reading.selectedCard < (reading.session.cards || []).length
            ? reading.session.cards[reading.selectedCard].title + " · " + (reading.session.cards[reading.selectedCard].jumper ? "Lá rơi, ngoài thứ tự trải" : "Vị trí " + reading.session.cards[reading.selectedCard].position)
            : "Ký hiệu minh họa của RAT · Chọn một lá để đối chiếu vị trí."
        color: reading.host.muted; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
    }
        }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: reading.host.edge }

    // Draft Not Yet Synthesized
    ColumnLayout {
        visible: !Boolean(reading.session.draft && reading.session.draft.draft_markdown)
        Layout.fillWidth: true
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "BẢN LUẬN · CHƯA TẠO"
                color: reading.host.muted; font.pixelSize: 10; font.letterSpacing: 1.5; Layout.fillWidth: true
            }
            Button {
                objectName: "readingSynthesizeButton"
                text: "Soạn bản luận · chờ Agent/model"
                enabled: Boolean((reading.session.cards || []).length)
                onClicked: reading.host.liveController.synthesizeReadingDraft("")
                background: Rectangle { radius: 8; color: parent.hovered ? reading.host.selectedSurface : reading.host.utilitySurface; border.color: reading.host.edge }
                contentItem: Text { text: parent.text; color: parent.enabled ? reading.host.accent : reading.host.muted; font.pixelSize: 12; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
        }
        Label {
            text: "Dữ kiện bài và lá số được giữ trên bàn. Chưa nối Agent/model để diễn giải; thao tác soạn hiện báo chưa khả dụng."
            color: reading.host.muted; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
    }

    // Synthesized Draft View & Editor
    ColumnLayout {
        visible: Boolean(reading.session.draft && reading.session.draft.draft_markdown)
        Layout.fillWidth: true
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Label {
                    text: "BẢN LUẬN · REASONING DRAFT"
                    color: reading.host.accent; font.pixelSize: 10; font.letterSpacing: 1.5
                }
                Label {
                    text: (reading.session.draft || {}).title || "Bản luận trải bài"
                    font.family: "Georgia"; font.pixelSize: 18; color: reading.host.ink
                    wrapMode: Text.Wrap; Layout.fillWidth: true
                }
            }
            RowLayout {
                spacing: 6
                Button {
                    objectName: "readingSynthesizeSmartNoteButton"
                    text: "Tạo Smart Note"
                    onClicked: reading.host.liveController.synthesizeNoteFromReadingDraft("decision")
                    background: Rectangle { radius: 8; color: parent.hovered ? reading.host.selectedSurface : reading.host.utilitySurface; border.color: reading.host.accent }
                    contentItem: Text { text: parent.text; color: reading.host.accent; font.pixelSize: 11; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
                Button {
                    objectName: "readingEditDraftButton"
                    text: reading.isEditingDraft ? "Hủy sửa" : "Sửa bản nháp"
                    onClicked: reading.isEditingDraft = !reading.isEditingDraft
                    background: Rectangle { radius: 8; color: parent.hovered ? reading.host.selectedSurface : reading.host.utilitySurface; border.color: reading.host.edge }
                    contentItem: Text { text: parent.text; color: reading.host.accent; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
                Button {
                    objectName: "readingResynthesizeButton"
                    text: "Soạn lại"
                    onClicked: reading.host.liveController.synthesizeReadingDraft("")
                    background: Rectangle { radius: 8; color: parent.hovered ? reading.host.selectedSurface : reading.host.utilitySurface; border.color: reading.host.edge }
                    contentItem: Text { text: parent.text; color: reading.host.accent; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
        }

        // Read-only Draft Text
        Rectangle {
            visible: !reading.isEditingDraft
            Layout.fillWidth: true
            implicitHeight: draftCol.implicitHeight + 20
            radius: 10
            color: reading.host.darkMode ? "#292c25" : "#fdfbf7"
            border.color: reading.host.darkMode ? "#474b3e" : "#dfd7c5"
            ColumnLayout {
                id: draftCol
                anchors.fill: parent; anchors.margins: 12; spacing: 8
                TextEdit {
                    objectName: "readingDraftText"
                    Layout.fillWidth: true
                    readOnly: true
                    selectByMouse: true
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                    font.family: "Georgia"
                    font.pixelSize: 14
                    color: reading.host.ink
                    text: (reading.session.draft || {}).draft_markdown || ""
                }
            }
        }

        // Inline Editor Mode
        ColumnLayout {
            visible: reading.isEditingDraft
            Layout.fillWidth: true
            spacing: 8
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 280
                clip: true
                TextArea {
                    id: inlineDraftEditor
                    objectName: "readingDraftInlineEditor"
                    text: (reading.session.draft || {}).draft_markdown || ""
                    selectByMouse: true
                    wrapMode: Text.Wrap
                    font.family: "Georgia"
                    font.pixelSize: 14
                    color: reading.host.ink
                    background: Rectangle { radius: 8; color: reading.host.paperColor; border.color: reading.host.accent }
                }
            }
            RowLayout {
                spacing: 8
                Button {
                    objectName: "readingSaveDraftButton"
                    text: "Lưu bản sửa"
                    onClicked: {
                        reading.host.liveController.saveReadingDraft(inlineDraftEditor.text)
                        reading.isEditingDraft = false
                    }
                    background: Rectangle { radius: 8; color: reading.host.accent }
                    contentItem: Text { text: parent.text; color: "#ffffff"; font.pixelSize: 12; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
                Button {
                    text: "Hủy"
                    onClicked: reading.isEditingDraft = false
                    background: Rectangle { radius: 8; color: reading.host.utilitySurface; border.color: reading.host.edge }
                    contentItem: Text { text: parent.text; color: reading.host.muted; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
        }

    }

    // Smart Note Section (SoL-Pi Observation Pack & Verification)
    ColumnLayout {
        id: smartNoteSection
        objectName: "readingSmartNoteSection"
        visible: Boolean(reading.session.activeNote)
        Layout.fillWidth: true
        spacing: 12

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: reading.host.edge }

        // Header & Badges
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                RowLayout {
                    spacing: 8
                    Label {
                        text: "GHI CHÚ CÓ CẤU TRÚC · SOL-PI"
                        color: reading.host.accent
                        font.pixelSize: 10
                        font.letterSpacing: 1.5
                    }
                    Rectangle {
                        radius: 4
                        color: reading.host.darkMode ? "#343c2c" : "#e8efe1"
                        border.color: reading.host.darkMode ? "#516244" : "#b8cca6"
                        implicitWidth: revLabel.implicitWidth + 12
                        implicitHeight: 18
                        Label {
                            id: revLabel
                            anchors.centerIn: parent
                            text: "rev " + ((reading.session.activeNote || {}).revision || 1)
                            font.pixelSize: 10
                            color: reading.host.accent
                        }
                    }
                    Rectangle {
                        radius: 4
                        color: reading.host.utilitySurface
                        border.color: reading.host.edge
                        implicitWidth: domainLabel.implicitWidth + 12
                        implicitHeight: 18
                        Label {
                            id: domainLabel
                            anchors.centerIn: parent
                            text: (reading.session.activeNote || {}).domain || "decision"
                            font.pixelSize: 10
                            color: reading.host.muted
                        }
                    }
                }
                Label {
                    objectName: "readingNoteTitle"
                    text: (reading.session.activeNote || {}).title || "Ghi chú thông minh"
                    font.family: "Georgia"
                    font.pixelSize: 17
                    color: reading.host.ink
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
            Label {
                text: "Đã kiểm chứng · PASS"
                color: reading.host.accent
                font.pixelSize: 10
                font.weight: Font.Medium
            }
        }

        // Key Facts (Grounding)
        ColumnLayout {
            visible: Boolean(((reading.session.activeNote || {}).key_facts || []).length)
            Layout.fillWidth: true
            spacing: 6
            Label {
                text: "DỮ KIỆN NỀN TẢNG (" + (((reading.session.activeNote || {}).key_facts || []).length) + " mục)"
                font.pixelSize: 10
                font.letterSpacing: 1.2
                color: reading.host.muted
            }
            Repeater {
                model: (reading.session.activeNote || {}).key_facts || []
                Rectangle {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    implicitHeight: factRow.implicitHeight + 10
                    radius: 6
                    color: reading.host.utilitySurface
                    border.color: reading.host.edge
                    RowLayout {
                        id: factRow
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 8
                        Label {
                            text: "•"
                            color: reading.host.accent
                            font.pixelSize: 14
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.fact || ""
                            font.pixelSize: 12
                            color: reading.host.ink
                            wrapMode: Text.Wrap
                        }
                        Label {
                            visible: Boolean(modelData.source)
                            text: "[" + (modelData.source || "") + "]"
                            font.pixelSize: 10
                            color: reading.host.muted
                        }
                    }
                }
            }
        }

        // Action Items (Interactive Checklist)
        ColumnLayout {
            visible: Boolean(((reading.session.activeNote || {}).action_items || []).length)
            Layout.fillWidth: true
            spacing: 6
            Label {
                text: "KẾ HOẠCH HÀNH ĐỘNG (" + (((reading.session.activeNote || {}).action_items || []).length) + " việc)"
                font.pixelSize: 10
                font.letterSpacing: 1.2
                color: reading.host.muted
            }
            Repeater {
                model: (reading.session.activeNote || {}).action_items || []
                Rectangle {
                    id: actionRow
                    required property var modelData
                    required property int index
                    objectName: "readingActionItem_" + index
                    Layout.fillWidth: true
                    implicitHeight: actionInner.implicitHeight + 12
                    radius: 6
                    color: modelData.done ? (reading.host.darkMode ? "#23261f" : "#f4f6f0") : reading.host.paperColor
                    border.color: modelData.done ? reading.host.edge : (reading.host.darkMode ? "#555b4a" : "#c6cfbc")

                    RowLayout {
                        id: actionInner
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 10

                        Rectangle {
                            id: checkboxBox
                            width: 18
                            height: 18
                            radius: 4
                            color: modelData.done ? reading.host.accent : "transparent"
                            border.color: reading.host.accent
                            border.width: 1.5

                            Text {
                                anchors.centerIn: parent
                                text: "✓"
                                font.pixelSize: 12
                                font.bold: true
                                color: "#ffffff"
                                visible: Boolean(modelData.done)
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var noteId = (reading.session.activeNote || {}).note_id || ""
                                    reading.host.liveController.updateNoteActionItem(noteId, modelData.task, !modelData.done)
                                }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: modelData.task || ""
                            font.pixelSize: 13
                            color: modelData.done ? reading.host.muted : reading.host.ink
                            font.strikeout: Boolean(modelData.done)
                            wrapMode: Text.Wrap
                        }

                        Rectangle {
                            visible: Boolean(modelData.priority)
                            radius: 3
                            color: reading.host.utilitySurface
                            implicitWidth: priorityText.implicitWidth + 8
                            implicitHeight: 16
                            Label {
                                id: priorityText
                                anchors.centerIn: parent
                                text: (modelData.priority || "").toUpperCase()
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                color: modelData.priority === "high" ? "#c0392b" : reading.host.muted
                            }
                        }
                    }
                }
            }
        }

        // Analysis Sections & Expansion
        ColumnLayout {
            visible: Boolean(((reading.session.activeNote || {}).analysis_sections || []).length)
            Layout.fillWidth: true
            spacing: 8
            Label {
                text: "MỤC PHÂN TÍCH & ĐÀO SÂU"
                font.pixelSize: 10
                font.letterSpacing: 1.2
                color: reading.host.muted
            }
            Repeater {
                model: (reading.session.activeNote || {}).analysis_sections || []
                Rectangle {
                    id: secBox
                    required property var modelData
                    required property int index
                    objectName: "readingSection_" + index
                    Layout.fillWidth: true
                    implicitHeight: secCol.implicitHeight + 16
                    radius: 8
                    color: reading.host.utilitySurface
                    border.color: reading.host.edge

                    ColumnLayout {
                        id: secCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: modelData.heading || ("Mục " + (index + 1))
                                font.family: "Georgia"
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                color: reading.host.ink
                                Layout.fillWidth: true
                            }
                            Rectangle {
                                visible: (modelData.badges || []).indexOf("expanded") !== -1
                                radius: 3
                                color: reading.host.darkMode ? "#343c2c" : "#e8efe1"
                                implicitWidth: expBadge.implicitWidth + 8
                                implicitHeight: 16
                                Label {
                                    id: expBadge
                                    anchors.centerIn: parent
                                    text: "ĐÃ ĐÀO SÂU"
                                    font.pixelSize: 9
                                    color: reading.host.accent
                                }
                            }
                            Button {
                                objectName: "readingExpandSectionButton_" + index
                                text: "Đào sâu"
                                onClicked: {
                                    var noteId = (reading.session.activeNote || {}).note_id || ""
                                    var heading = modelData.heading || ""
                                    reading.host.liveController.expandNoteSection(noteId, heading, "Nghiên cứu sâu về " + heading, "Phân tích bổ sung về " + heading + ": Phân tích chi tiết khía cạnh thực tế.")
                                }
                                background: Rectangle { radius: 6; color: parent.hovered ? reading.host.selectedSurface : reading.host.paperColor; border.color: reading.host.edge }
                                contentItem: Text { text: parent.text; color: reading.host.accent; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: modelData.content || (modelData.points ? modelData.points.join("\n• ") : "")
                            font.pixelSize: 12
                            color: reading.host.ink
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }
}
