"""Shared geometry and opt-in boundaries; never live UI/model evidence."""
import pytest
from rat.ui.surface_geometry import Rect
from rat.ui.speech_placement import place_speech
from rat.engine.mini_settings import DEFAULTS
from rat.engine.mini_cloud import CloudModelClient
from rat.mini import MiniSession


@pytest.mark.parametrize('area', [Rect(0, 0, 1440, 900), Rect(-640, -100, 640, 600), Rect(0, 0, 320, 480)])
@pytest.mark.parametrize('edge', ['left', 'right', 'top', 'bottom'])
@pytest.mark.parametrize('size', [(80, 84), (96, 100), (176, 176)])
def test_speech_fits_without_covering_its_anchor(area, edge, size):
    w, h = size
    anchor = Rect(area.x + (16 if edge == 'left' else area.width-w-16),
                  area.y + (16 if edge == 'top' else area.height-h-16), w, h)
    result = place_speech(area, anchor, 340, 300, preferred_side=edge)
    body = result.body
    assert area.x <= body.x < body.right <= area.right
    assert area.y <= body.y < body.bottom <= area.bottom
    assert body.right <= anchor.x or body.x >= anchor.right or body.bottom <= anchor.y or body.y >= anchor.bottom
    second = place_speech(area, anchor, 76, 48, preferred_side=result.side)
    assert second.side == result.side


def test_default_mini_never_reads_a_model_key_or_attempts_cloud(tmp_path):
    calls = []
    client = CloudModelClient(dict(DEFAULTS), key_reader=lambda *args: calls.append(args))
    with pytest.raises(ValueError, match='mini_llm_disabled'):
        client.chat_with_meta([], [])
    assert client.calls == 0 and calls == []
    session = MiniSession(dict(DEFAULTS, roots=[str(tmp_path)]))
    for text in ('hmm', 'find notes then translate hello'):
        response = session.submit(text)
        assert response.pending_input_request and response.completion_status == 'needs_input'
        assert session.client.calls == 0
    assert not session.runtime.plan_tasks and not session.runtime.use_live_model


def test_mini_uses_optical_bounds_and_preserves_home_for_both_surfaces():
    from rat.ui.mini_placement import place_look
    area=Rect(0,0,1440,900); home=(1240,680)
    ink=Rect(20,12,133,134);mouth=(80,70)
    small=place_look(area,home,160,70,ink_bounds=ink,mouth=mouth)
    composer=place_look(area,home,580,94,side=small.side,ink_bounds=ink,mouth=mouth)
    assert small.rat==composer.rat
    assert small.panel.right==composer.panel.right==small.rat.x+ink.x-8
    assert small.panel.y+small.panel.height/2==small.rat.y+mouth[1]
    assert composer.panel.y+composer.panel.height/2==composer.rat.y+mouth[1]
