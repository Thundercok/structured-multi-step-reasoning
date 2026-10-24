import QtQuick
import QtQuick.Window

// App-owned symbols share one 24x24 optical grid/stroke. Native application icons stay native.
Image {
    id: glyph
    property string name: "file"
    property color color: "#62695e"
    width: 16
    height: 16
    readonly property real dpr: Math.max(2, Math.ceil(Window.window ? Window.window.devicePixelRatio : 2))
    sourceSize.width: Math.max(16, Math.ceil(width * dpr))
    sourceSize.height: Math.max(16, Math.ceil(height * dpr))
    fillMode: Image.PreserveAspectFit
    smooth: true
    mipmap: true
    cache: true
    Accessible.ignored: true
    readonly property var paths: ({
        "file": '<path d="M14.5 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-11z"/><path d="M14 2.5V8.5h5.5"/><path d="M8.5 13h7 M8.5 16.5h4.5"/>',
        "pdf": '<path d="M14.5 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-11z"/><path d="M14 2.5V8.5h5.5"/><rect x="7" y="11.8" width="10" height="6.2" rx="1.6" fill="' + color + '" fill-opacity="0.2" stroke="' + color + '" stroke-width="1.35"/><path d="M9.5 14.9h5" stroke-width="1.6"/>',
        "paperclip": '<path d="m20.4 11.2-7.9 7.9a5.2 5.2 0 0 1-7.35-7.35l8.1-8.1a3.4 3.4 0 0 1 4.8 4.8l-8.1 8.1a1.6 1.6 0 0 1-2.26-2.26l7.3-7.3"/>',
        "eye": '<path d="M2.5 12s3.4-6.2 9.5-6.2 9.5 6.2 9.5 6.2-3.4 6.2-9.5 6.2S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.6"/>',
        "folder": '<path d="M3.5 6.5a2 2 0 0 1 2-2h4.1a2 2 0 0 1 1.55.74l1.25 1.56a1 1 0 0 0 .78.38h5.32a2 2 0 0 1 2 2v8.32a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
        "search": '<circle cx="10.8" cy="10.8" r="6.3"/><path d="m15.6 15.6 4.4 4.4"/>',
        "send": '<path d="M20.5 3.5 10.2 13.8"/><path d="m20.5 3.5-6.6 17-3.7-6.7-6.7-3.7z"/>',
        "sparkle": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/>',
        "close": '<path d="m6.5 6.5 11 11 M17.5 6.5l-11 11"/>',
        "minus": '<path d="M5.5 12h13"/>',
        "plus": '<path d="M5.5 12h13 M12 5.5v13"/>',
        "arrow-up": '<path d="M12 19.6V5.8 M6.8 11 12 5.8l5.2 5.2"/>',
        "arrow-left": '<path d="M19 12H5 M10.5 6.5 5 12l5.5 5.5"/>',
        "arrow-right": '<path d="M5 12h14 M13.5 6.5 19 12l-5.5 5.5"/>',
        "enter": '<path d="M19.5 5.5v8.5H5 M9.5 9.5 5 14l4.5 4.5"/>',
        "chevron-down": '<path d="m6.5 9.5 5.5 5.5 5.5-5.5"/>',
        "chevron-up": '<path d="m6.5 14.5 5.5-5.5 5.5 5.5"/>',
        "chevron-right": '<path d="m9.5 6.5 5.5 5.5-5.5 5.5"/>',
        "copy": '<rect x="8.5" y="8.5" width="11.5" height="12" rx="2"/><path d="M15.5 8.5V5.5a2 2 0 0 0-2-2H5.5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3"/>',
        "check": '<path d="m5 12.5 4.2 4.2L19 7"/>',
        "external": '<path d="M13.5 4h6.5v6.5 M20 4l-8.5 8.5 M9.5 4.5H6a2 2 0 0 0-2 2v11.5a2 2 0 0 0 2 2h11.5a2 2 0 0 0 2-2v-3.5"/>',
        "stop": '<rect x="6.5" y="6.5" width="11" height="11" rx="2.2" fill="' + color + '" stroke="none"/>',
        "warning": '<path d="m12 3.5 9.5 16.5h-19z M12 9.5v4.5 M12 17h.01"/>'
    })
    source: "data:image/svg+xml," + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
        + (paths[name] || paths.file) + '</svg>')
}
