"""Interaction contracts, not native UI acceptance or translation quality evidence."""
from rat.ui.look_interaction import LookInteraction
from rat.ui.mini_presentation import look_projection


def test_copy_is_silent_and_latest_wins_without_changing_reading_pose():
    look = LookInteraction()
    look.enable()
    look.receive('first')
    assert look.surface == 'hidden'
    look.read('head')
    look.receive('second')
    look.receive('third')
    assert look.surface == 'reading' and look.pose == 'head'
    assert look.take_pending().text == 'third'
    assert look.pending is None


def test_close_keeps_pending_and_monitoring_but_pause_and_disable_clear():
    look = LookInteraction()
    look.enable(); look.read(); look.receive('keep me'); look.close()
    assert look.pending.text == 'keep me' and look.monitoring == 'on'
    look.pause()
    look.receive('ignored')
    assert look.pending is None
    look.enable(); look.receive('new'); look.disable()
    assert look.surface == 'hidden' and look.pending is None


def test_preview_is_bounded_and_does_not_change_the_source():
    source = 'a long source with whitespace\n' * 100
    look = LookInteraction(); look.enable(); look.receive(source); look.peek()
    assert len(look.hint()) < 100
    assert look.take_pending().text == source


def test_pose_and_current_text_are_stable_when_new_copy_arrives():
    look = LookInteraction(); look.enable(); look.read('head')
    state = dict(hasWorkbench=True, phase='result', text='Kết quả đang đọc.', view='translation')
    before = look_projection(dict(state, **look.snapshot(has_result=True)))
    look.receive('A new paragraph. ' * 30)
    after = look_projection(dict(state, **look.snapshot(has_result=True)))
    assert before == after
    busy = look_projection(dict(state, busy=True, **look.snapshot(has_result=True)))
    assert busy['lookVariant'] == before['lookVariant'] == 'C'
    look.close()
    assert look_projection(dict(state, **look.snapshot(has_result=True)))['lookText'] == ''
