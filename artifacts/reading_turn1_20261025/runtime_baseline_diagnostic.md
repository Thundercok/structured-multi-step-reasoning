# Runtime regression diagnostic

Three failures in tests/test_assistant_runtime.py also reproduce with
create_reading_capability monkeypatched to an empty Capability before pytest
collection. No source files were changed for this diagnostic.

- test_context_includes_followup_and_selected_member: StopIteration looking for Runtime context message.
- test_malformed_native_messages_are_recorded_failures[message2]: expected invalid_model_output, observed empty_model_response.
- test_malformed_native_messages_are_recorded_failures[message3]: same mismatch.

Diagnostic result: 3 failed, 5 passed. New reading_session/kernel/natal focused
suite: 30 passed. Original combined log: tools_tests.log.
