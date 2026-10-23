import QtQuick

// App-owned symbols share one grid/stroke. Native application icons stay native.
Image {
    id: glyph
    property string name: "file"
    property color color: "#62695e"
    width: 16
    height: 16
    sourceSize.width: Math.ceil(width * 2)
    sourceSize.height: Math.ceil(height * 2)
    fillMode: Image.PreserveAspectFit
    smooth: true
    cache: true
    Accessible.ignored: true
    readonly property var paths: ({
        "file": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z M14 3v6h6 M8 13h8 M8 17h5"/>',
        "pdf": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z M14 3v6h6 M8 13h8 M8 17h5"/>',
        "eye": '<path d="M3 12s3-6 9-6 9 6 9 6-3 6-9 6-9-6-9-6z"/><circle cx="12" cy="12" r="2.5"/>',
        "folder": '<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M10 12l3 3-3 3"/>',
        "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
        "close": '<path d="m6 6 12 12 M18 6 6 18"/>',
        "minus": '<path d="M5 12h14"/>',
        "plus": '<path d="M5 12h14 M12 5v14"/>',
        "arrow-up": '<path d="M12 20V4 M6 10l6-6 6 6"/>',
        "arrow-left": '<path d="M20 12H4 M10 6l-6 6 6 6"/>',
        "arrow-right": '<path d="M4 12h16 M14 6l6 6-6 6"/>',
        "enter": '<path d="M20 5v9H5 M10 9l-5 5 5 5"/>',
        "chevron-down": '<path d="m6 9 6 6 6-6"/>',
        "chevron-up": '<path d="m6 15 6-6 6 6"/>',
        "chevron-right": '<path d="m9 6 6 6-6 6"/>',
        "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3"/>',
        "check": '<path d="m5 12 4 4L19 6"/>',
        "external": '<path d="M13 4h7v7 M20 4l-9 9 M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
        "stop": '<rect x="6" y="6" width="12" height="12" rx="2" fill="' + color + '" stroke="none"/>',
        "warning": '<path d="m12 3 10 18H2z M12 9v5 M12 17h.01"/>'
    })
    source: "data:image/svg+xml," + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        + (paths[name] || paths.file) + '</svg>')
}
