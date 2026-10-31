import sys
import os
import json
import time
from pathlib import Path

# Ensure dependencies are available
os.environ.setdefault('PYTHONPATH', '.:/private/tmp/rat-mini-offline-mt-deps')
if '/private/tmp/rat-mini-offline-mt-deps' not in sys.path:
    sys.path.insert(0, '/private/tmp/rat-mini-offline-mt-deps')
if '.' not in sys.path:
    sys.path.insert(0, '.')

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest

from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk

def run_verification():
    audit_dir = Path("audit/rat_lite_0531_live_20261031")
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    
    # Configure clean first-run settings
    settings = dict(DEFAULTS,
                    roots=['/Volumes/NO NAME'],
                    setup_completed=False,
                    permission_hello_version=1,
                    source_language='en',
                    target_language='vi',
                    free_fallback=False)
    
    view, controller = create_mini_desk(settings)
    root = view.rootObject()
    view.show()
    view.requestActivate()
    
    def pump(ms=300):
        for _ in range(max(1, ms // 30)):
            QTest.qWait(30)
            app.processEvents()

    pump(500)
    
    results = {}
    
    # -------------------------------------------------------------
    # Journey 1: Setup / Welcome (auxiliary)
    # -------------------------------------------------------------
    print("Verifying Journey 1: Setup / Welcome (auxiliary)...")
    snap1 = controller.snapshot
    assert snap1['surface'] == 'welcome', f"Expected surface welcome, got {snap1['surface']}"
    assert root.property('auxiliary') is True, "Expected auxiliary == True"
    mascot = root.findChild(QObject, 'mascotCrop')
    assert mascot.property('visible') is False, "Mascot should not be visible in auxiliary welcome"
    
    # Save screenshot
    img1 = view.grabWindow()
    img1_path = audit_dir / "journey1_welcome_auxiliary.png"
    img1.save(str(img1_path))
    assert img1_path.stat().st_size > 0
    results['journey1'] = {
        'status': 'PASS',
        'surface': snap1['surface'],
        'auxiliary': True,
        'window_geom': [view.x(), view.y(), view.width(), view.height()],
        'screenshot': str(img1_path)
    }
    print(f"Journey 1 PASS: window at {view.x()},{view.y()} size {view.width()}x{view.height()}")
    
    # Transition: click 'Bắt đầu'
    setup_err = controller.completeSetup()
    assert not setup_err, f"Setup error: {setup_err}"
    pump(600)
    
    # -------------------------------------------------------------
    # Journey 2: Hotkey Helper Connection (rat-hotkey) & Composer
    # -------------------------------------------------------------
    print("Verifying Journey 2: Hotkey Helper Connection & Composer...")
    snap2 = controller.snapshot
    assert snap2['setupCompleted'] is True
    assert root.property('auxiliary') is False
    assert mascot.property('visible') is True
    assert mascot.property('width') == 144 and mascot.property('height') == 144
    composer = root.findChild(QObject, 'composer')
    assert composer.property('visible') is True
    
    # Wait for hotkey to report READY if starting
    t0 = time.time()
    while controller.snapshot['hotkeyStarting'] and time.time() - t0 < 5.0:
        pump(100)
        
    snap2_ready = controller.snapshot
    print(f"Hotkey status: '{snap2_ready.get('hotkeyStatus')}' (shortcutLabel: {snap2_ready.get('shortcutLabel')})")
    assert not snap2_ready.get('hotkeyStatus'), f"Hotkey error: {snap2_ready.get('hotkeyStatus')}"
    
    img2 = view.grabWindow()
    img2_path = audit_dir / "journey2_composer_hotkey_ready.png"
    img2.save(str(img2_path))
    assert img2_path.stat().st_size > 0
    results['journey2'] = {
        'status': 'PASS',
        'setupCompleted': True,
        'hotkeyStatus': snap2_ready.get('hotkeyStatus'),
        'shortcutLabel': snap2_ready.get('shortcutLabel'),
        'mascot_visible': mascot.property('visible'),
        'mascot_size': [mascot.property('width'), mascot.property('height')],
        'composer_visible': composer.property('visible'),
        'screenshot': str(img2_path)
    }
    print("Journey 2 PASS: Composer active, companion anchored at 144x144, hotkey ready.")

    # -------------------------------------------------------------
    # Journey 3: Spotlight File Finding (find_files)
    # -------------------------------------------------------------
    print("Verifying Journey 3: Spotlight File Finding (find_files)...")
    controller.setComposerDraft("Tìm project_scope.md")
    pump(100)
    controller.submitDraft()
    
    t0 = time.time()
    while controller.snapshot['busy'] and time.time() - t0 < 10.0:
        pump(100)
        
    snap3 = controller.snapshot
    assert snap3['phase'] == 'result', f"Expected phase result, got {snap3['phase']}"
    assert snap3['view'] == 'finder', f"Expected view finder, got {snap3['view']}"
    hits = snap3.get('finderHits', [])
    assert len(hits) > 0, f"Expected finder hits, got {hits}"
    print(f"Found {len(hits)} hits: {[h['title'] for h in hits]}")
    
    # Test keyboard navigation
    root.selectFile(0)
    pump(100)
    assert root.property('selectedFinderIndex') == 0
    
    # Layout check: composer y is > 0 because results are placed above composer
    pump(200)
    print(f"Layout check: composer y={composer.property('y')}")
    assert composer.property('y') > 0, f"Expected composer to be placed below result sheet, got y={composer.property('y')}"
    
    # Verify Mở file capability
    assert snap3.get('hasWorkbench') is True
    
    img3 = view.grabWindow()
    img3_path = audit_dir / "journey3_finder_results.png"
    img3.save(str(img3_path))
    assert img3_path.stat().st_size > 0
    results['journey3'] = {
        'status': 'PASS',
        'phase': snap3['phase'],
        'view': snap3['view'],
        'hit_count': len(hits),
        'hits': [{'title': h['title'], 'path': h['path']} for h in hits],
        'selected_index': root.property('selectedFinderIndex'),
        'layout': {
            'composer_y': composer.property('y'),
            'mascot_visible': mascot.property('visible'),
            'mascot_size': [mascot.property('width'), mascot.property('height')]
        },
        'screenshot': str(img3_path)
    }
    print("Journey 3 PASS: Finder results displayed above composer with keyboard selection.")

    # -------------------------------------------------------------
    # Journey 4: Offline Translation (translate_text)
    # -------------------------------------------------------------
    print("Verifying Journey 4: Offline Translation (translate_text)...")
    controller.setComposerDraft("Dịch: The little rat is reading a book.")
    pump(100)
    controller.submitDraft()
    
    t0 = time.time()
    while controller.snapshot['busy'] and time.time() - t0 < 15.0:
        pump(100)
        
    snap4 = controller.snapshot
    assert snap4['phase'] == 'result', f"Expected phase result, got {snap4['phase']}: {snap4.get('status')}"
    assert snap4['view'] == 'translation', f"Expected view translation, got {snap4['view']}"
    translated_text = snap4.get('text', '').strip()
    print(f"Translation result: '{translated_text}'")
    assert translated_text, "Translation result text was empty"
    assert snap4['interactionExtent'] == 'compact', "Should start in compact extent"
    assert mascot.property('width') == 144 and mascot.property('height') == 144
    assert composer.property('y') > 0, "Compact translation bubble should be above composer"
    
    img4_compact = view.grabWindow()
    img4_compact_path = audit_dir / "journey4_offline_translation_compact.png"
    img4_compact.save(str(img4_compact_path))
    assert img4_compact_path.stat().st_size > 0
    
    # Toggle expanded
    controller.setExpanded(True)
    pump(300)
    snap4_exp = controller.snapshot
    assert snap4_exp['interactionExtent'] == 'expanded'
    assert mascot.property('width') == 144 and mascot.property('height') == 144
    
    img4_expanded = view.grabWindow()
    img4_expanded_path = audit_dir / "journey4_offline_translation_expanded.png"
    img4_expanded.save(str(img4_expanded_path))
    assert img4_expanded_path.stat().st_size > 0
    
    # Toggle compact back
    controller.setExpanded(False)
    pump(300)
    assert controller.snapshot['interactionExtent'] == 'compact'
    
    results['journey4'] = {
        'status': 'PASS',
        'phase': snap4['phase'],
        'view': snap4['view'],
        'translation': translated_text,
        'compact_mascot_size': [mascot.property('width'), mascot.property('height')],
        'compact_screenshot': str(img4_compact_path),
        'expanded_screenshot': str(img4_expanded_path)
    }
    print("Journey 4 PASS: Offline translation rendered in compact/expanded bubble.")

    # Save verification JSON
    (audit_dir / "verification_report.json").write_text(json.dumps(results, indent=2))
    print(f"\nAll 4 journeys PASSED! Verification report written to {audit_dir / 'verification_report.json'}")

    from rat.os.mini_hotkey import close_hotkey_registrations
    close_hotkey_registrations('quit')
    view.hide()
    pump(100)


if __name__ == '__main__':
    run_verification()
