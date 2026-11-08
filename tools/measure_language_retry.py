"""Count how often the assistant answers a Vietnamese question in Chinese.

Runs the real model through the real runtime on a temporary, empty state directory, so
questions about files reach the "nothing found" path, where this failure was first seen.

Run: python tools/measure_language_retry.py --model qwen3:4b-instruct --out runs.json
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

QUESTIONS = (
    # Nothing to find: the assistant has to say so.
    "tiền cọc phòng trọ là bao nhiêu?",
    "bảng điểm học kỳ trước của mình để ở đâu?",
    "tìm giúp mình hợp đồng thuê nhà",
    "tài liệu nào nói về lương tháng 13?",
    "đề thi cuối kỳ môn giải tích năm ngoái có gì?",
    "mình đã lưu file chứng minh nhân dân chưa?",
    "có slide nào về mạng nơ-ron không?",
    "hóa đơn tiền điện tháng 9 là bao nhiêu?",
    # General knowledge, where a model trained heavily on Chinese can drift.
    "Lý Bạch là ai?",
    "Tết Trung thu có nguồn gốc từ đâu?",
    "giải thích thuyết tương đối cho học sinh cấp 3",
    "Tam Quốc Diễn Nghĩa kể về chuyện gì?",
    "trà ô long khác trà xanh thế nào?",
    "vì sao bầu trời có màu xanh?",
    "Khổng Tử có những tư tưởng chính nào?",
    "học tiếng Trung nên bắt đầu từ đâu?",
    "cách nấu phở bò ngon",
    "đại dịch 1918 bắt đầu như thế nào?",
    # Technical questions.
    "thuật toán tìm kiếm nhị phân hoạt động ra sao?",
    "khác nhau giữa TCP và UDP là gì?",
    "transformer trong học sâu là gì?",
    "viết hàm Python đảo ngược một chuỗi",
    # Short and casual, including without accents.
    "chào bạn",
    "bạn làm được gì?",
    "hôm nay mình nên học gì?",
    "cho minh hoi file bao cao o dau",
    "tai lieu nay noi gi",
    "ban giup minh duoc khong",
    # Arithmetic and follow-up style.
    "15% của 2.400.000 là bao nhiêu?",
    "nếu mỗi tháng tiết kiệm 2 triệu thì một năm được bao nhiêu?",
)
RETRY_MARK = "Yêu cầu bắt buộc"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    os.environ["RAT_STATE_DIR"] = tempfile.mkdtemp(prefix="rat_language_")
    os.environ["RAT_DB_PATH"] = str(Path(os.environ["RAT_STATE_DIR"]) / "index.db")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.engine.language_check import CJK_REGEX, is_mainly_cjk, is_vietnamese
    from rat.engine.slm import SLMEngine

    runtime = AssistantRuntime(model_client=SLMEngine(model=args.model), discover_tools=True)
    call_model = runtime._call_model
    rows = []
    for question in QUESTIONS:
        calls = {"retries": 0, "cjk_drafts": 0}

        def counting(goal, trajectory, _calls=calls, **context):
            _calls["retries"] += RETRY_MARK in goal
            decision = call_model(goal, trajectory, **context)
            _calls["cjk_drafts"] += bool(CJK_REGEX.search(decision.final_answer or ""))
            return decision

        runtime._call_model = counting
        started = time.time()
        response = runtime.run(question)
        rows.append({"question": question, "vietnamese": is_vietnamese(question), **calls,
                     "answer": response.answer, "error": response.error,
                     "answer_has_cjk": bool(CJK_REGEX.search(response.answer or "")),
                     "answer_mainly_cjk": is_mainly_cjk(response.answer or ""),
                     "seconds": round(time.time() - started, 1)})
        row = rows[-1]
        print(f"{row['seconds']:6.1f}s retry={row['retries']} draft_cjk={row['cjk_drafts']} "
              f"cjk={row['answer_has_cjk']} err={row['error']} | {question}", flush=True)
        if args.out:
            args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    done = [row for row in rows if row["error"] != "timeout"]
    print(json.dumps({"model": args.model, "questions": len(rows), "timeouts": len(rows) - len(done),
                      "not_detected_vietnamese": sum(not row["vietnamese"] for row in rows),
                      "retries": sum(row["retries"] > 0 for row in rows),
                      "any_cjk_draft": sum(row["cjk_drafts"] > 0 for row in rows),
                      "answer_has_cjk": sum(row["answer_has_cjk"] for row in rows),
                      "language_mismatch": sum(row["error"] == "language_mismatch" for row in rows)}, indent=1))


if __name__ == "__main__":
    main()
