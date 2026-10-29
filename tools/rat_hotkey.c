/* Carbon hotkey owner with its own event loop, independent of Qt/Cocoa. */
#include <Carbon/Carbon.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#ifndef RAT_BUILD_ID
#error "Build with tools/build_rat_mini_hotkey.sh to supply the matching identity"
#endif

static EventHotKeyID identity = { 'rmin', 1 };
static Boolean down = false;
static pid_t owner_pid = 0;

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

/* GUI launchers may close stdin even while the owning app is alive. Track the
   actual parent instead: pipe EOF must not silently unregister the shortcut. */
static void *watch_parent(void *unused) {
    for (;;) {
        if (getppid() != owner_pid) _exit(0);
        usleep(250000);
    }
}

int main(int argc, char **argv) {
    /* Only the supported Space chords; reject partial/unknown arguments. */
    if (argc != 3) return 2;
    char *key_end, *mod_end;
    long key = strtol(argv[1], &key_end, 10);
    long modifiers = strtol(argv[2], &mod_end, 10);
    if (*key_end || *mod_end || key != kVK_Space ||
        (modifiers != (optionKey | shiftKey) && modifiers != (controlKey | optionKey) &&
         modifiers != (controlKey | shiftKey))) return 2;
    setvbuf(stdout, NULL, _IONBF, 0);
    owner_pid = getppid();
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
    status = RegisterEventHotKey((UInt32)key, (UInt32)modifiers, identity,
        GetApplicationEventTarget(), kEventHotKeyExclusive, &hotkey);
    if (status) { fprintf(stderr, "RegisterEventHotKey OSStatus=%d\n", (int)status); return 1; }
    pthread_t watcher;
    if (pthread_create(&watcher, NULL, watch_parent, NULL)) return 1;
    pthread_detach(watcher);
    printf("READY SELECT2 %s %ld %ld\n", RAT_BUILD_ID, key, modifiers);
    /* RunApplicationEventLoop is unavailable on 64-bit macOS. Use the
       Carbon dispatcher directly; the helper owns no windows or UI. */
    for (;;) {
        EventRef event = NULL;
        status = ReceiveNextEvent(0, NULL, kEventDurationForever, true, &event);
        if (status) {
            fprintf(stderr, "ReceiveNextEvent OSStatus=%d\n", (int)status);
            break;
        }
        SendEventToEventTarget(event, GetEventDispatcherTarget());
        ReleaseEvent(event);
    }
    UnregisterEventHotKey(hotkey);
    RemoveEventHandler(handler);
    return status ? 1 : 0;
}
