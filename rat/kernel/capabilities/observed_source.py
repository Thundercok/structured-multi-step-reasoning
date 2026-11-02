"""One integrity/expiry boundary for tools consuming a captured snippet."""
import hashlib
import time

SOURCE_REF_SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'artifact_id': {'type': 'string', 'maxLength': 128},
    'revision': {'type': 'integer', 'minimum': 1}}, 'required': ['artifact_id', 'revision']}


def observed_capture(pin, context):
    artifact = context['artifact_store'].get(pin['artifact_id'])
    if artifact is None or artifact.kind != 'captured_text' or artifact.revision != pin['revision']:
        raise ValueError('stale_source_ref')
    if time.time() - artifact.created_at > 1800:
        raise ValueError('source_expired')
    text = artifact.payload['text']
    if hashlib.sha256(text.encode()).hexdigest() != artifact.payload.get('source_sha256'):
        raise ValueError('source_integrity_mismatch')
    return artifact
