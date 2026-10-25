"""Persisted observations keep their existing inline answer/trace presentation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

from rat.kernel import ActionDispatcher, ArtifactStore
from rat.kernel.contracts import Artifact
from rat.kernel.registry import CapabilityRegistry, OperationDefinition
from rat.ui.assistant_presenter import source_panel


@pytest.mark.parametrize('returns_artifact', [False, True])
def test_reference_only_result_is_kept_without_a_separate_data_card(returns_artifact):
    app = QApplication.instance() or QApplication([])
    registry, store = CapabilityRegistry(), ArtifactStore()
    registry.register_operation(OperationDefinition(
        'observe_sample', 'Read a sample observation', {'type': 'object', 'properties': {}},
        lambda args, **ctx: Artifact('observed', 'sample', payload={'value': 7}) if returns_artifact else {'value': 7},
        artifact_kind='sample', present_result=False,
    ))
    result = ActionDispatcher(registry, store).execute_operation('observe_sample', {}, context={
        'turn_id': 'turn-1', 'execution_id': 'exec-1',
    })
    assert result.status == 'success' and store.get(result.artifact.id).payload == {'value': 7}
    assert source_panel([], artifacts=[result.artifact], registry=registry) is None
    app.processEvents()


def test_reference_observation_does_not_hide_an_existing_deliverable():
    app = QApplication.instance() or QApplication([])
    hidden = Artifact('reference', 'sample', payload={'value': 7}, provenance={'presentation': 'trace'})
    shown = Artifact('deliverable', 'sample', payload={'value': 9}, title='Kết quả')
    panel = source_panel([], artifacts=[hidden, shown], registry=CapabilityRegistry())
    assert [artifact.id for artifact in panel.artifacts] == ['deliverable']
    assert set(panel.renderers) == {'deliverable'}
    panel.close()
    panel.deleteLater()
    app.processEvents()
