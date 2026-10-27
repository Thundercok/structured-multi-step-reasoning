"""Headless ingress for a tool-enabled RAT profile, shared with main composition.

Rules compile unambiguous requests into one-action plans; they never execute
business logic. Ambiguity is an InputRequest, not a persistent UI mode.
"""
from dataclasses import dataclass, field
from pathlib import PurePath, Path
import re

from rat.kernel.contracts import InputRequest


LANGUAGES = {'tiếng việt':'vi', 'vietnamese':'vi', 'vi':'vi',
    'tiếng anh':'en', 'english':'en', 'en':'en', 'anh':'en',
    'tiếng nhật':'ja', 'japanese':'ja', 'ja':'ja',
    'tiếng hàn':'ko', 'korean':'ko', 'ko':'ko',
    'tiếng trung':'zh', 'chinese':'zh', 'zh':'zh',
    'tiếng pháp':'fr', 'french':'fr', 'fr':'fr',
    'tiếng đức':'de', 'german':'de', 'de':'de'}
TRANSLATE = re.compile(r'^(?:(?:hãy|giúp tôi|giúp mình|please)\s+)?(?:dịch|translate)\b', re.I)
FIND = re.compile(r'^(?:(?:hãy|giúp tôi|giúp mình|please)\s+)?(?:tìm(?:\s+kiếm)?|find|search(?:\s+for)?)\b', re.I)


@dataclass
class GoalRoute:
    kind: str
    operation: str | None = None
    args: dict = field(default_factory=dict)
    input_request: InputRequest | None = None
    rule: str = ''


class ToolGoalRouter:
    def __init__(self, operations, *, source_language='auto', target_language='vi', language_detector=None, roots=()):
        self.roots = tuple(str(Path(p).expanduser()) for p in roots)
        self.operations = frozenset(operations)
        self.defaults = dict(source_language=source_language, target_language=target_language)
        self.language_detector = language_detector

    def direct(self, operation, args, rule):
        if operation not in self.operations:
            return self.ask('Yêu cầu này chưa có công cụ trong phiên hiện tại.', rule='unavailable')
        return GoalRoute('direct', operation, args, rule=rule)

    @staticmethod
    def ask(prompt, *, supplied=None, field_name='intent', rule='clarify'):
        request = InputRequest('route_goal', supplied_inputs=supplied or {},
            missing_fields=[dict(name=field_name, required=True)], prompt=prompt)
        return GoalRoute('needs_input', input_request=request, rule=rule)

    def resolve(self, text, *, pending=None, tool_input=None, input_kind='typed', previous=None):
        text = text.strip()
        # Do not compile a compound goal into just its first tool. Translation
        # payloads and pasted passages remain data, including quoted commands.
        if input_kind == 'typed' and not TRANSLATE.match(text) and re.search(
                r'\b(?:rồi|sau đó|tiếp theo|và|then|and then|and)\s+'
                r'(?:tìm|dịch|sắp xếp|dọn|xem trước|lập|kiểm tra|so sánh|tóm tắt|'
                r'find|translate|organize|organise|preview|check|compare|summarize)\b', text, re.I):
            return GoalRoute('agent', rule='multi_step_goal')
        organizing = re.match(r'^(?:(?:hãy|giúp tôi|giúp mình|please)\s+)?(?:dọn|sắp xếp|organize|organise)\b', text, re.I)
        if organizing or (pending and pending.supplied_inputs.get('operation') == 'plan_folder_organization'):
            rule = ('month' if re.search(r'tháng|thời gian|month|date', text, re.I) else 'type')
            if pending and not organizing:
                rule = pending.supplied_inputs.get('args', {}).get('rule', rule)
            candidates = [p for p in self.roots if Path(p).name.casefold() in text.casefold() or p in text]
            if len(candidates) != 1:
                return self.ask('Bạn muốn sắp xếp thư mục nào? Gửi tên thư mục trong Cài đặt, hoặc dùng ⋯ → Sắp xếp thư mục…',
                    supplied={'operation':'plan_folder_organization','args':{'rule':rule}}, field_name='folder', rule='organization_folder')
            return self.direct('plan_folder_organization', {'folder':candidates[0], 'rule':rule}, 'organization_preview')
        translation = TRANSLATE.match(text)
        finding = FIND.match(text)
        # An explicit new instruction supersedes a clarification, except a short
        # answer selecting the intended action for an already supplied snippet.
        if pending and not (translation or finding):
            supplied = pending.supplied_inputs
            if supplied.get('operation'):
                operation = supplied['operation']
                args = dict(supplied.get('args', {}))
                args['text' if operation == 'translate_text' else 'query'] = text
                return self.direct(operation, args, 'clarification_value')
        if tool_input and not (translation or finding):
            missing = {v['name'] for v in tool_input.missing_fields}
            args = dict(tool_input.supplied_inputs)
            if 'source_language' in missing:
                language = LANGUAGES.get(text.casefold())
                if not language:
                    return GoalRoute('needs_input', input_request=tool_input, rule='language_still_missing')
                args['source_language'] = language
            elif 'text' in missing:
                args['text'] = text
            elif 'query' in missing:
                args['query'] = text
            else:
                return GoalRoute('needs_input', input_request=tool_input, rule='tool_input_still_missing')
            return self.direct(tool_input.operation_name, args, 'tool_input_continuation')
        original = (pending.supplied_inputs.get('original') if pending else None)
        if finding:
            query = text[finding.end():].strip(' :\n')
            if original and not query:
                query = original
            if not query:
                return self.ask('Bạn muốn tìm file nào?', supplied={'operation':'find_files'}, field_name='query')
            if re.search(r'\b(?:rồi|và|then)\s+(?:dịch|translate)\b', query, re.I):
                return GoalRoute('agent', rule='multi_step_goal')
            return self.direct('find_files', {'query':query}, 'explicit_find')
        if translation:
            body = text[translation.end():].strip(' :\n')
            args = dict(self.defaults)
            for label in sorted(LANGUAGES, key=len, reverse=True):
                match = re.match(r'^(?:sang|qua|to|into)\s+'+re.escape(label)+r'(?=$|[\s:])', body, re.I)
                if match:
                    args['target_language'] = LANGUAGES[label]
                    body = body[match.end():].strip(' :\n')
                    break
                suffix = re.search(r'\s+(?:sang|qua|to|into)\s+'+re.escape(label)+r'$', body, re.I)
                if suffix:
                    args['target_language'] = LANGUAGES[label]
                    body = body[:suffix.start()].strip()
                    break
            body = re.sub(r'^(?:đoạn này|đoạn sau|văn bản sau|this text)\s*:\s*', '', body, flags=re.I)
            if body.casefold() in ('đoạn này', 'đoạn sau', 'văn bản này', 'this', 'this text'):
                body = ''
            if not body and original:
                body = original
            if not body:
                return self.ask('Bạn gửi đoạn cần dịch nhé.', supplied={'operation':'translate_text','args':args}, field_name='text')
            if len(body)>1 and (body[0],body[-1]) in (('"','"'),("'","'"),('“','”')):
                body = body[1:-1]
            return self.direct('translate_text', dict(args,text=body), 'explicit_translate')
        if input_kind == 'file_reference':
            paths = [p for p in text.splitlines() if p.strip()]
            if len(paths) != 1:
                return self.ask('Bạn muốn tìm tệp nào trong các tệp vừa dán?',
                    supplied={'operation':'find_files'},field_name='query',rule='multiple_file_references')
            return self.direct('find_files', {'query':PurePath(paths[0]).name}, 'pasted_file_reference')
        if len(text) < 240 and '\n' not in text and re.search(r'\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|png|jpe?g|zip)\s*$',text,re.I):
            return self.direct('find_files', {'query':text}, 'filename')
        words = text.split()
        paragraph = '\n' in text or len(words) >= 18
        if not paragraph and len(words) <= 10 and re.match(r'^(?:báo cáo|tài liệu|file|tệp|report|document)\b',text,re.I):
            return self.direct('find_files', {'query':text}, 'file_description')
        if re.fullmatch(r'https?://\S+', text, re.I):
            return self.ask('Bạn gửi đoạn chữ cần dịch, hoặc tên tệp cần tìm nhé.', rule='url_needs_content')
        language = self.language_detector(text) if self.language_detector else None
        if input_kind == 'pasted_text' and (len(words) >= 2 or len(text) >= 12):
            return self.direct('translate_text', dict(self.defaults,text=text), 'pasted_passage')
        if language and language != self.defaults['target_language'] and (len(words) >= 2 or re.search(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]',text)):
            return self.direct('translate_text', dict(self.defaults,text=text), 'foreign_passage')
        if previous and previous.get('operation') == 'translate_text' and paragraph:
            return self.direct('translate_text', dict(self.defaults,text=text), 'translation_continuation')
        if previous and previous.get('operation') == 'find_files' and len(words) <= 8 and not paragraph:
            query = text
            if re.match(r'^(?:hôm|tuần|tháng|năm|trước|sau|yesterday|last)\b',text,re.I):
                query = previous.get('args',{}).get('query','') + ' ' + text
            return self.direct('find_files', {'query':query}, 'finder_continuation')
        return self.ask('Bạn muốn mình tìm file hay dịch đoạn vừa gửi?',
            supplied={'original':text}, rule='ambiguous_goal')
