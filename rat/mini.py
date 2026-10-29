"""RAT Mini product composition. No Qt, credentials, index scan or models at import."""
from pathlib import Path
import os
import re
import sys
import time
from uuid import uuid4

from rat.engine.assistant_runtime import AssistantRuntime, AgentResponse
from rat.engine.goal_routing import ToolGoalRouter
from rat.kernel.contracts import Artifact, ExecutionEvent
from rat.engine.execution import ExecutionRequest
from rat.engine.execution_service import AgentExecutionService
from rat.engine.local_finder import ScopePolicy, HybridFinder
from rat.engine.mini_cloud import CloudModelClient
from rat.engine.mini_settings import read_settings, state_directory
from rat.engine.snippet_translation import SnippetTranslator, detect_language
from rat.kernel.registry import CapabilityRegistry
from rat.kernel.profile import MINI_PROFILE
from rat.kernel.capabilities.file_finder import create_file_finder_capability
from rat.kernel.capabilities.translation import create_translation_capability
from rat.kernel.capabilities.source_analysis import create_source_analysis_capability
from rat.kernel.capabilities.folder_organizer import create_folder_organizer_capability
from rat.kernel.capabilities.mini_setup import create_mini_setup_capability
from rat.engine.folder_organization import FolderOrganizer


class MiniSession:
    def __init__(self, settings=None, *, artifact_store=None):
        self.settings = dict(settings) if settings is not None else read_settings()
        self.settings['llm_enabled'] = self.settings.get('llm_enabled') is True
        if not self.settings['llm_enabled'] and self.settings.get('translation_provider') == 'llm':
            self.settings['translation_provider'] = 'automatic'
        self.scopes = ScopePolicy(self.settings['roots'])
        # This release is Spotlight-only. Deferred semantic code is never imported.
        self.semantic = None
        self.finder = HybridFinder(self.scopes)
        self.client = CloudModelClient(self.settings)
        registry = CapabilityRegistry()
        registry.register_capability(create_file_finder_capability(self.finder))
        registry.register_capability(create_folder_organizer_capability(FolderOrganizer(self.scopes, state_directory()/"organization")))
        registry.register_capability(create_mini_setup_capability(self.settings))
        registry.register_capability(create_translation_capability(SnippetTranslator(self.settings, self.client)))
        registry.register_capability(create_source_analysis_capability(self.client))
        self.runtime = AssistantRuntime(registry=registry, profile=MINI_PROFILE, model_client=self.client,
                                        artifact_store=artifact_store,
                                        use_live_model=self.settings['llm_enabled'], enable_observation_pack=True,
                                        plan_tasks=self.settings['llm_enabled'], planner_operations_only=True)
        # One compact planner, at most two tool steps, then a reserved finish.
        # Fits the existing four-request/2048-generated-token cloud budget.
        self.runtime.max_reasoning_steps = 3
        self.service = AgentExecutionService(self.runtime)
        self.router = ToolGoalRouter([t.name for t in registry.to_tool_definitions()],
            source_language=self.settings['source_language'], target_language=self.settings['target_language'],
            language_detector=detect_language, roots=self.settings["roots"])
        self.pending_route = None
        self.previous_goal = None
        self._agent_goal = None
        self._agent_history = []

    def submit(self, query, *, input_kind='typed', cancel=lambda: False, on_event=None, progress=None, on_step=None, source_ref=None):
        if cancel():
            return AgentResponse('', [], 0, 0, 0, error='cancelled')
        route = self.router.resolve(query, pending=self.pending_route,
            tool_input=self.runtime.dispatcher.state.pending_input_request,
            input_kind=input_kind, previous=self.previous_goal, source_ref=source_ref)
        analysis = re.match(r'^(?:hãy\s+|please\s+)?(tóm tắt|giải thích|thuật ngữ|viết lại|summarize|explain|terms|rewrite)\b', query, re.I) if input_kind == 'typed' else None
        if analysis and route.kind != 'agent':
            if source_ref:
                mode = {'tóm tắt':'summary', 'summarize':'summary', 'giải thích':'explanation',
                    'explain':'explanation', 'thuật ngữ':'terms', 'terms':'terms',
                    'viết lại':'rewrite', 'rewrite':'rewrite'}[analysis.group(1).casefold()]
                route = self.router.direct('analyze_captured_text', {'source_ref':dict(source_ref),
                    'mode':mode, 'instruction':query[:2000], 'target_language':self.settings['target_language']}, 'source_analysis')
            else:
                route = self.router.ask('Hãy lấy một đoạn chữ bằng phím tắt hoặc dán ảnh trước để giữ nguồn cho câu trả lời.', rule='analysis_source_missing')
        if route.kind == 'agent' and not self.settings['llm_enabled']:
            route = self.router.ask(
                'Bạn muốn làm bước nào trước? Gửi tên file cần tìm, đoạn cần dịch hoặc thư mục cần sắp xếp.',
                rule='mini_step_clarification')
        if source_ref and route.input_request and route.input_request.supplied_inputs.get('operation') == 'translate_text':
            route = self.router.direct('translate_text', {
                **route.input_request.supplied_inputs.get('args', {}),
                'source_ref': dict(source_ref)}, 'observed_source_translation')
        resume_agent = bool(self._agent_goal and
            route.rule in ('tool_input_continuation', 'tool_input_still_missing', 'language_still_missing'))
        agent_goal = self.settings['llm_enabled'] and (route.kind == 'agent' or resume_agent or (
            route.rule == 'ambiguous_goal' and input_kind == 'typed'))
        if agent_goal:
            self.pending_route = None
            if resume_agent:
                self._agent_history.append({'role': 'user', 'content': query})
            else:
                self.clear_pending()
                self._agent_goal, self._agent_history = query, []
            sources = [{'type': 'allowed_folder', 'path': str(root)} for root in self.scopes.roots]
            if source_ref:
                source = self.runtime.artifact_store.get(source_ref.get('artifact_id'))
                if source is None or source.kind != 'captured_text' or source.revision != source_ref.get('revision'):
                    return AgentResponse('', [], 0, 0, 0, error='stale_source_ref')
                sources.append({'type': 'captured_text', 'source_ref': dict(source_ref),
                                'text': source.payload['text']})
            response = self.execute(query=self._agent_goal, cancel=cancel,
                on_event=on_event, progress=progress, on_step=on_step,
                input_context={'history': self._agent_history[-4:],
                    'previous_sources': sources})
            if response.pending_input_request:
                self._agent_history.append({'role': 'assistant',
                    'content': response.pending_input_request.prompt})
                self._agent_history = self._agent_history[-4:]
            else:
                self._agent_goal, self._agent_history = None, []
            response.controller_decisions.append({'route': 'agent', 'rule':
                'agent_continuation' if resume_agent else route.rule})
            return response
        self.pending_route = route.input_request if route.kind == 'needs_input' and route.input_request.operation_name == 'route_goal' else None
        if route.kind == 'needs_input':
            request = route.input_request
            execution_id, turn_id = 'mini-'+uuid4().hex, 'turn-'+uuid4().hex
            artifact = self.runtime.artifact_store.get(request.id)
            if artifact is None:
                artifact = Artifact(request.id, 'input_request', 1, request.to_dict(), status='waiting_input')
                self.runtime.artifact_store.put(artifact)
            event = ExecutionEvent('waiting_input', request.operation_name,
                artifact_id=artifact.id, payload=request.to_dict(), execution_id=execution_id, turn_id=turn_id)
            if on_event:
                on_event(event)
            self.client.begin_turn()
            return AgentResponse(request.prompt, [], 0, 0, 0, completion_status='needs_input',
                pending_input_request=request, artifacts=[artifact], execution_id=execution_id, turn_id=turn_id)
        response = self.execute(route.operation if route.kind == 'direct' else None, route.args,
            query=query, cancel=cancel, on_event=on_event, progress=progress, on_step=on_step)
        response.controller_decisions.append({'route':route.kind, 'rule':route.rule, 'operation':route.operation})
        return response

    def execute(self, operation=None, args=None, *, query='', cancel=lambda: False, on_event=None, progress=None, input_context=None, on_step=None):
        if not operation and not self.settings['llm_enabled']:
            # A missed UI route must never activate the shared model fallback.
            return AgentResponse('', [], 0, 0, 0, error='mini_llm_disabled')
        if operation:
            self.pending_route = None
            self._agent_goal, self._agent_history = None, []
        pending = self.runtime.dispatcher.state.pending_input_request
        if operation and pending:
            # Each explicit UI submission contains a new complete input snapshot.
            # Do not silently merge stale text/ref from an abandoned request.
            self.runtime.dispatcher.dismiss_input(pending.id)
        self.client.begin_turn()
        deadline = time.monotonic() + (300 if operation == 'index_files' else 45)
        cancelled = lambda: cancel() or time.monotonic() >= deadline
        response = self.service.execute(ExecutionRequest(
            query=query or operation or '', execution_id='mini-' + uuid4().hex,
            turn_id='turn-' + uuid4().hex, origin='ui_action' if operation else 'chat',
            requested_action={'name': operation, 'args': args or {}} if operation else None,
            context={'user_initiated': bool(operation), 'progress': progress, **(input_context or {})},
            budget={'deadline_s': 300 if operation == 'index_files' else 45, 'max_generated_tokens': 2048}),
            should_cancel=cancelled, on_event=on_event, on_progress=progress, on_step=on_step)
        response.is_live_model = bool(not operation and self.client.responses)
        response.qa_telemetry = {**(response.qa_telemetry or {}),
            'mini_execution_path': 'direct_tool' if operation else 'model_loop',
            'model_requests': self.client.calls, 'model_responses': self.client.responses}
        if not response.error and not response.pending_input_request and operation in ('find_files','translate_text'):
            self.previous_goal = {'operation':operation, 'args':dict(args or {})}
        return response

    def clear_pending(self):
        self.pending_route = None
        self._agent_goal, self._agent_history = None, []
        request = self.runtime.dispatcher.state.pending_input_request
        if request:
            self.runtime.dispatcher.dismiss_input(request.id)
