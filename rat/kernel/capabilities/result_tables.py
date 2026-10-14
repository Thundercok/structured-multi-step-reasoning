"""Small RAT-AI-02 slice: model-selected tables whose cells bind to real results."""
from __future__ import annotations

import copy
import math

from rat.kernel.registry import Capability, OperationDefinition
from rat.kernel.view_spec import ViewBlock, ViewSpec


def resolve_cell(store, ref):
    # Require an active artifact as well as the explicitly requested revision.
    current = store.get(ref["artifact_id"])
    artifact = store.get(ref["artifact_id"], ref["revision"])
    if current is None or artifact is None or artifact.status != "ready":
        raise ValueError("Nguồn bảng không còn trong phiên hoặc phiên bản không tồn tại.")
    value = artifact.payload
    for part in ref["field"].split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdecimal() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ValueError(f"Trường nguồn không tồn tại: {ref['field']}")
    if value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("Ô bảng phải tham chiếu một giá trị đơn, không phải cả đối tượng hoặc danh sách.")
    if isinstance(value, str) and len(value) > 2000:
        raise ValueError("Nội dung ô quá dài; chọn đoạn trích hoặc trường ngắn hơn.")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("Giá trị số nguồn không hữu hạn.")
    return copy.deepcopy(value), {**ref, "kind": artifact.kind,
                                  "title": artifact.title, "historical": current.revision != artifact.revision}


def view_result_table(artifact, context):
    payload = artifact.payload
    refs = payload["source_refs"]
    sources = "\n".join(f"{ref['title']} · phiên bản {ref['revision']}" +
                        (" (bản cũ lúc ghép)" if ref["historical"] else "") for ref in refs)
    return ViewSpec(1, artifact.id, artifact.revision, title=payload["title"], blocks=[
        ViewBlock("summary", {"title": payload["title"],
                              "text": f"Ghép từ {len(refs)} kết quả đã có."}),
        ViewBlock("table", {"headers": payload["headers"], "rows": payload["rows"]}),
        ViewBlock("details", {"title": "Nguồn dữ liệu", "content": sources}),
    ])


def create_result_tables_capability():
    cap = Capability("result_tables", "Bảng so sánh kết quả",
                     "Chọn và ghép dữ liệu thật từ nhiều kết quả trong hội thoại.")

    def compose(args, **context):
        store = context["artifact_store"]
        columns = len(args["headers"])
        rows, cell_refs, sources = [], [], {}
        for row in args["rows"]:
            if len(row) != columns:
                raise ValueError("Mỗi hàng phải có đúng số ô tương ứng với tiêu đề cột.")
            values, references = [], []
            for cell in row:
                value, ref = resolve_cell(store, cell)
                values.append(value)
                references.append(ref)
                sources[(ref["artifact_id"], ref["revision"])] = {
                    key: ref[key] for key in ("artifact_id", "revision", "kind", "title", "historical")}
            rows.append(values)
            cell_refs.append(references)
        return {"title": args["title"], "headers": args["headers"], "rows": rows,
                "cell_refs": cell_refs, "source_refs": list(sources.values()),
                "assessment": "source_copy_only_labels_are_model_authored"}

    ref_schema = {"type": "object", "properties": {
        "artifact_id": {"type": "string"},
        "revision": {"type": "integer", "minimum": 1},
        "field": {"type": "string", "description": "Scalar payload path, e.g. items.0.page or result."},
    }, "required": ["artifact_id", "revision", "field"]}
    cap.register_operation(OperationDefinition(
        "compose_result_table",
        "Compose a comparison or selected-data table from observed artifact revisions. "
        "Every cell must reference a real scalar payload field; inspect_artifact first if needed. "
        "Use dot paths and zero-based list indexes, e.g. items.0.snippet. "
        "No literal cells or invented data. Headers/title are your labels, not verified interpretations. "
        "This copies selected values; it does not calculate differences or assert comparability.",
        {"type": "object", "properties": {
            "title": {"type": "string", "maxLength": 150},
            "headers": {"type": "array", "items": {"type": "string", "maxLength": 80},
                        "minItems": 1, "maxItems": 6},
            "rows": {"type": "array", "items": {"type": "array", "items": ref_schema,
                      "minItems": 1, "maxItems": 6}, "minItems": 1, "maxItems": 12},
        }, "required": ["title", "headers", "rows"]}, compose,
        artifact_kind="result_table", view_factory=view_result_table))
    return cap
