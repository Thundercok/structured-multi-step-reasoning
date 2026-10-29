/* Carbon hotkey owner with its own event loop, independent of Qt/Cocoa. */
#include <Carbon/Carbon.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static EventHotKeyID identity = { 'rmin', 1 };
static Boolean down = false;

static OSStatus pressed(EventHandlerCallRef next, EventRef event, void *context) {
    EventHotKeyID received = {0};
    OSStatus status = GetEventParameter(event, kEventParamDirectObject,
        typeEventHotKeyID, NULL, sizeof(received), NULL, &received);
    if (status || received.signature != identity.signature || received.id != identity.id)
        return eventNotHandledErr;
    if (GetEventKind(event) == kEventHotKeyPressed) {
        if (!down) { down = true; puts("SELECTION"); }
    } else if (GetEventKind(event) == kEventHotKeyReleased && down) {
        down = false;
    } else return eventNotHandledErr;
    return noErr;
}

/* EOF also cleans up if the GUI crashes or is forcibly terminated. */
static void *watch_parent(void *unused) {
    while (getchar() != EOF) {}
    _exit(0);
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    ProcessSerialNumber process = {0, kCurrentProcess};
    OSStatus status = TransformProcessType(&process, kProcessTransformToUIElementApplication);
    if (status) { fprintf(stderr, "TransformProcessType OSStatus=%d\n", (int)status); return 1; }
    EventTypeSpec specs[] = {
        { kEventClassKeyboard, kEventHotKeyPressed },
        { kEventClassKeyboard, kEventHotKeyReleased },
    };
    EventHandlerRef handler = NULL;
    status = InstallApplicationEventHandler(pressed, 2, specs, NULL, &handler);
    if (status) { fprintf(stderr, "InstallApplicationEventHandler OSStatus=%d\n", (int)status); return 1; }
    EventHotKeyRef hotkey = NULL;
    status = RegisterEventHotKey(kVK_Space, optionKey | shiftKey, identity,
        GetApplicationEventTarget(), 0, &hotkey);
    if (status) { fprintf(stderr, "RegisterEventHotKey OSStatus=%d\n", (int)status); return 1; }
    pthread_t watcher;
    if (pthread_create(&watcher, NULL, watch_parent, NULL)) return 1;
    pthread_detach(watcher);
    puts("READY SELECT1");
    /* RunApplicationEventLoop is unavailable on 64-bit macOS. Use the
       Carbon dispatcher directly; the helper owns no windows or UI. */
    for (;;) {
        EventRef event = NULL;
        status = ReceiveNextEvent(0, NULL, kEventDurationForever, true, &event);
        if (status) break;
        SendEventToEventTarget(event, GetEventDispatcherTarget());
        ReleaseEvent(event);
    }
    UnregisterEventHotKey(hotkey);
    RemoveEventHandler(handler);
    return 0;
}
