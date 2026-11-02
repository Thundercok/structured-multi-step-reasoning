import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: desk
    required property var controller
    property bool darkMode: false
    readonly property var snap: controller.snapshot
    readonly property var result: snap.result || ({})
    readonly property var steps: result.steps || []
    readonly property bool hasResult: steps.length > 0

    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    readonly property color muted: darkMode ? "#b7bdaf" : "#62695e"
    readonly property color paperColor: darkMode ? "#272d25" : "#fdfdf9"
    readonly property color inputColor: darkMode ? "#2b3227" : "#fdfefb"
    readonly property color backingColor: darkMode ? "#1f241c" : "#e8ece1"
    readonly property color edge: darkMode ? "#424d39" : "#e0e5d8"
    readonly property color accent: darkMode ? "#c0d2a7" : "#4f6740"
    readonly property color accentText: darkMode ? "#24301b" : "#fafcf5"
    readonly property color warningInk: darkMode ? "#e4bb89" : "#916329"
    readonly property color wrongInk: darkMode ? "#dbaa9f" : "#a15e50"
    readonly property color selectedSurface: darkMode ? "#2d3727" : "#edf4e8"
    readonly property color selectedEdge: darkMode ? "#46593d" : "#b5ceaa"
    readonly property color utilitySurface: darkMode ? "#242820" : "#f0f4ea"
    readonly property color hoverSurface: darkMode ? "#2a3125" : "#f1f6ed"
    readonly property string monoFont: Qt.platform.os === "osx" ? "Menlo" : "monospace"

    function verdictText(verdict) { return verdict === "correct" ? "Đúng" : (verdict === "wrong" ? "Sai" : "") }
    function verdictColor(verdict) { return verdict === "wrong" ? wrongInk : accent }

    color: backingColor

    component Card: Rectangle {
        color: desk.paperColor
        radius: 12
        border.width: 1
        border.color: desk.edge
    }

    component Chip: Rectangle {
        id: chip
        property string label: ""
        property bool active: false
        signal clicked()
        implicitHeight: 30
        implicitWidth: chipLabel.implicitWidth + 24
        radius: 15
        color: active ? desk.selectedSurface : (chipMouse.containsMouse ? desk.hoverSurface : desk.utilitySurface)
        border.width: 1
        border.color: active ? desk.selectedEdge : desk.edge
        opacity: enabled ? 1 : 0.5
        Accessible.role: Accessible.Button
        Accessible.name: label
        Label {
            id: chipLabel
            anchors.centerIn: parent
            text: chip.label
            font.pixelSize: 12
            font.weight: chip.active ? Font.DemiBold : Font.Medium
            color: chip.active ? desk.accent : desk.ink
        }
        MouseArea {
            id: chipMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.clicked()
        }
    }

    component Metric: ColumnLayout {
        property string value: ""
        property string caption: ""
        spacing: 1
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Label { text: parent.value; font.pixelSize: 18; font.weight: Font.DemiBold; color: desk.ink }
        Label { text: parent.caption; font.pixelSize: 11; color: desk.muted }
    }

    component StepCard: Card {
        id: stepCard
        required property var step
        property bool open: true
        Layout.fillWidth: true
        implicitHeight: stepColumn.implicitHeight + 28
        ColumnLayout {
            id: stepColumn
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Label {
                    text: stepCard.step.label
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: desk.ink
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                Label {
                    visible: stepCard.step.verdict !== ""
                    text: desk.verdictText(stepCard.step.verdict)
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: desk.verdictColor(stepCard.step.verdict)
                }
                Label {
                    text: stepCard.open ? "Thu gọn" : "Xem chi tiết"
                    font.pixelSize: 11
                    color: desk.muted
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: stepCard.open = !stepCard.open
                    }
                }
            }
            Label {
                text: "Đáp án: " + (stepCard.step.answer || "chưa có")
                font.pixelSize: 15
                font.weight: Font.Medium
                color: desk.ink
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
            Label {
                text: stepCard.step.tokens + " token · " + stepCard.step.seconds + " giây · độ tin cậy " + stepCard.step.confidence
                font.pixelSize: 11
                color: desk.muted
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
            Label {
                visible: stepCard.step.decision !== ""
                text: stepCard.step.decision
                font.pixelSize: 12
                color: desk.accent
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
            Rectangle {
                visible: stepCard.open
                Layout.fillWidth: true
                implicitHeight: detail.implicitHeight + 20
                radius: 8
                color: desk.utilitySurface
                Label {
                    id: detail
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                    text: stepCard.step.code || stepCard.step.text
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    font.family: stepCard.step.code ? desk.monoFont : ""
                    font.pixelSize: 12
                    color: desk.ink
                }
            }
            Label {
                visible: stepCard.open && stepCard.step.code !== ""
                text: (stepCard.step.toolOk ? "Máy chạy code ra: " : "Code bị lỗi: ") + stepCard.step.toolOutput
                textFormat: Text.PlainText
                font.family: desk.monoFont
                font.pixelSize: 12
                color: stepCard.step.toolOk ? desk.accent : desk.wrongInk
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
        }
    }

    ScrollView {
        id: scroller
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: scroller.availableWidth
            spacing: 14
            Item { implicitHeight: 6 }

            ColumnLayout {
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 2
                Label { text: "Phòng suy luận"; font.pixelSize: 24; font.weight: Font.DemiBold; color: desk.ink }
                Label {
                    text: "Xem cách mô hình chọn hướng giải, chạy thêm hay dừng, và tốn bao nhiêu token."
                    font.pixelSize: 13
                    color: desk.muted
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
            }

            Card {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                implicitHeight: inputColumn.implicitHeight + 32
                ColumnLayout {
                    id: inputColumn
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
                    spacing: 12
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        Repeater {
                            model: desk.snap.examples
                            Chip {
                                required property var modelData
                                required property int index
                                objectName: "example" + index
                                label: modelData.label
                                active: desk.snap.question === modelData.text
                                enabled: !desk.snap.busy
                                onClicked: desk.controller.useExample(index)
                            }
                        }
                    }
                    TextArea {
                        id: questionInput
                        objectName: "questionInput"
                        Layout.fillWidth: true
                        Layout.minimumHeight: 84
                        placeholderText: "Nhập một bài cần tính nhiều bước, hoặc chọn một ví dụ ở trên"
                        placeholderTextColor: desk.muted
                        wrapMode: TextArea.Wrap
                        font.pixelSize: 14
                        color: desk.ink
                        enabled: !desk.snap.busy
                        padding: 12
                        background: Rectangle {
                            radius: 8
                            color: desk.inputColor
                            border.width: 1
                            border.color: questionInput.activeFocus ? desk.selectedEdge : desk.edge
                        }
                        onTextChanged: if (text !== desk.snap.question) desk.controller.editQuestion(text)
                        Connections {
                            target: desk.controller
                            function onChanged() {
                                if (questionInput.text !== desk.snap.question)
                                    questionInput.text = desk.snap.question
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Chip { objectName: "modePolicy"; label: "Bộ điều phối"; active: desk.snap.mode === "policy"; enabled: !desk.snap.busy; onClicked: desk.controller.setMode("policy") }
                        Chip { objectName: "modeLadder"; label: "Bậc thang"; active: desk.snap.mode === "ladder"; enabled: !desk.snap.busy; onClicked: desk.controller.setMode("ladder") }
                        Chip { objectName: "modeCompare"; label: "So sánh 3 cách"; active: desk.snap.mode === "compare"; enabled: !desk.snap.busy; onClicked: desk.controller.setMode("compare") }
                        Item { Layout.fillWidth: true }
                        Button {
                            id: runButton
                            objectName: "runButton"
                            text: desk.snap.busy ? "Dừng" : "Giải"
                            enabled: desk.snap.busy || desk.snap.question.trim().length > 0
                            opacity: enabled ? 1 : 0.5
                            padding: 9
                            leftPadding: 22
                            rightPadding: 22
                            hoverEnabled: true
                            contentItem: Label {
                                text: runButton.text
                                color: desk.accentText
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                            }
                            background: Rectangle { radius: 9; color: desk.accent; opacity: runButton.hovered ? 0.88 : 1 }
                            onClicked: desk.snap.busy ? desk.controller.cancel() : desk.controller.submit()
                        }
                    }
                }
            }

            RowLayout {
                visible: desk.snap.busy
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                spacing: 10
                BusyIndicator { running: desk.snap.busy; implicitWidth: 22; implicitHeight: 22 }
                Label { objectName: "statusLabel"; text: desk.snap.status; font.pixelSize: 13; color: desk.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }

            Label {
                visible: desk.snap.error !== ""
                text: desk.snap.error
                color: desk.wrongInk
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                Layout.leftMargin: 26
                Layout.rightMargin: 26
            }

            Card {
                visible: desk.hasResult
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                implicitHeight: summaryColumn.implicitHeight + 32
                ColumnLayout {
                    id: summaryColumn
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
                    spacing: 10
                    RowLayout {
                        visible: desk.result.mode !== "compare"
                        Layout.fillWidth: true
                        spacing: 10
                        Label {
                            objectName: "finalAnswer"
                            text: desk.result.finalAnswer || (desk.snap.busy ? "Đang giải…" : "Chưa có đáp án")
                            font.pixelSize: 30
                            font.weight: Font.DemiBold
                            color: desk.ink
                        }
                        Label {
                            visible: desk.result.finalVerdict !== ""
                            text: desk.verdictText(desk.result.finalVerdict) + " · đáp án đúng là " + desk.result.expected
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: desk.verdictColor(desk.result.finalVerdict)
                            Layout.alignment: Qt.AlignBaseline
                        }
                        Item { Layout.fillWidth: true }
                    }
                    Label {
                        text: desk.result.reason || ""
                        font.pixelSize: 13
                        color: desk.muted
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    Flow {
                        visible: desk.result.mode !== "compare"
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: desk.result.path || []
                            RowLayout {
                                required property var modelData
                                required property int index
                                spacing: 6
                                Rectangle {
                                    radius: 6
                                    color: desk.selectedSurface
                                    border.width: 1
                                    border.color: desk.selectedEdge
                                    implicitHeight: 24
                                    implicitWidth: pathLabel.implicitWidth + 16
                                    Label { id: pathLabel; anchors.centerIn: parent; text: parent.parent.modelData; font.pixelSize: 11; font.weight: Font.Medium; color: desk.accent }
                                }
                                Label {
                                    visible: parent.index < (desk.result.path || []).length - 1
                                    text: "→"
                                    font.pixelSize: 12
                                    color: desk.muted
                                }
                            }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Metric { value: String(desk.result.tokens || 0); caption: "Token sinh ra" }
                        Metric { value: String(desk.result.promptTokens || 0); caption: "Token đầu vào" }
                        Metric { value: String(desk.result.calls || 0); caption: "Lần gọi mô hình" }
                        Metric { value: desk.snap.busy ? "Đang chạy" : desk.result.seconds + " giây"; caption: "Thời gian" }
                    }
                }
            }

            GridLayout {
                visible: desk.hasResult
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                columns: desk.result.mode === "compare" && scroller.availableWidth > 860 ? desk.steps.length : 1
                columnSpacing: 12
                rowSpacing: 12
                Repeater {
                    model: desk.steps
                    StepCard {
                        required property var modelData
                        required property int index
                        step: modelData
                        open: desk.result.mode === "compare" || index === desk.steps.length - 1
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                    }
                }
            }

            Label {
                text: "Quy tắc và ngưỡng lấy từ thử nghiệm phát triển trên 45 câu GSM8K, chưa phải kết quả thí nghiệm chính. Điểm tin cậy có thể cao cả khi đáp án sai."
                      + (desk.hasResult ? "\nĐã ghi log vào " + desk.snap.logPath : "")
                font.pixelSize: 11
                color: desk.muted
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                Layout.leftMargin: 26
                Layout.rightMargin: 26
            }
            Item { implicitHeight: 10 }
        }
    }
}
