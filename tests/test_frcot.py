"""
tests/test_frcot.py — Comprehensive Unit & Integration Test Suite for FR-CoT.
Validates:
1. Faceted Query Decomposition (MFQD)
2. Adaptive Multi-Way RRF (M-RRF)
3. Information Sufficiency Evaluation (Offline Reflection)
4. Zero-Cloud Corrective Cascading (Offline CRAG)
5. Structured Reasoning Trace (CoT)
6. End-to-End FR-CoT Search & Latency
7. Multi-Document Knowledge Synthesis
"""

import os
import sys
import time
import unittest
from pathlib import Path

from rat.config import config
from rat.crawler.db import Database
from rat.engine.corrective_retriever import CorrectiveRetriever, corrective_retriever
from rat.engine.hybrid_search import SearchEngine
from rat.engine.multi_way_rrf import FacetResult, MultiWayRRF, multi_way_rrf
from rat.engine.qa_engine import qa_engine
from rat.engine.query_decomposer import QueryDecomposer, RetrievalPlan, query_decomposer
from rat.engine.reasoning_trace import ReasoningStep, ReasoningTrace
from rat.engine.sufficiency_evaluator import SufficiencyEvaluator, SufficiencyReport, sufficiency_evaluator


class TestFRCoTArchitecture(unittest.TestCase):

    def setUp(self) -> None:
        self.test_db_path = "/tmp/test_frcot.db"
        p = Path(self.test_db_path)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

        self.db = Database(self.test_db_path)
        self.engine = SearchEngine(self.db)

        # Populate sample multi-modal dataset
        # 1. Financial report downloaded from Telegram
        self.doc_telegram = {
            "file_path": "/tmp/Bao_Cao_Q3_Telegram.pdf",
            "file_name": "Bao_Cao_Q3_Telegram.pdf",
            "file_ext": ".pdf",
            "file_size": 2048,
            "created_at": time.time() - 86400 * 2,
            "modified_at": time.time() - 86400 * 2,
            "md5_hash": "hash_tele_01",
            "content_text": (
                "Báo cáo tài chính quý 3 năm 2026. Doanh thu tăng trưởng 35%.\n"
                "[File Provenance]: Tải qua ứng dụng / Ứng dụng tạo: Telegram | Tải từ trang web / Nguồn: t.me/finance"
            ),
            "summary": "Báo cáo Q3 từ Telegram",
            "indexed_at": time.time(),
        }

        # 2. Scanned receipt image with Apple Vision OCR & stamps
        self.doc_receipt = {
            "file_path": "/tmp/Bien_Lai_Thue_Nha.jpg",
            "file_name": "Bien_Lai_Thue_Nha.jpg",
            "file_ext": ".jpg",
            "file_size": 4096,
            "created_at": time.time() - 86400 * 4,
            "modified_at": time.time() - 86400 * 4,
            "md5_hash": "hash_receipt_02",
            "content_text": (
                "Biên lai thu tiền thuê nhà tháng 8. Số tiền: 15.000.000 VNĐ.\n"
                "Đã thanh toán đủ. Có chữ ký và con dấu đỏ xác nhận.\n"
                "Visual Concepts (VI): hóa đơn, biên lai, chữ ký, con dấu\n"
                "Visual Concepts (EN): receipt, invoice, stamp, signature"
            ),
            "summary": "Biên lai tiền thuê nhà có chữ ký",
            "indexed_at": time.time(),
        }

        # 3. Source code file
        self.doc_code = {
            "file_path": "/tmp/dsa_sorting.py",
            "file_name": "dsa_sorting.py",
            "file_ext": ".py",
            "file_size": 1024,
            "created_at": time.time() - 86400 * 10,
            "modified_at": time.time() - 86400 * 10,
            "md5_hash": "hash_code_03",
            "content_text": (
                "def quicksort(arr):\n    # Bài tập môn DSA cấu trúc dữ liệu và giải thuật\n    return arr"
            ),
            "summary": "Code Python bài tập DSA",
            "indexed_at": time.time(),
        }

        self.db.upsert_document(self.doc_telegram)
        self.db.upsert_document(self.doc_receipt)
        self.db.upsert_document(self.doc_code)

    def tearDown(self) -> None:
        p = Path(self.test_db_path)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    def test_faceted_query_decomposition(self) -> None:
        """Verify orthogonal decomposition into OS facets."""
        # Query combining Type + Provenance + Temporal + Lexical
        q = "Tìm file pdf báo cáo tải từ Telegram tuần trước"
        plan = self.engine.decomposer.decompose(q, allow_slm=False)

        self.assertIn("lexical", plan.active_facets)
        self.assertIn("provenance", plan.active_facets)
        self.assertIn("temporal", plan.active_facets)
        self.assertIn("type", plan.active_facets)
        self.assertEqual(plan.source_app, "Telegram")
        self.assertIn(".pdf", plan.extensions)
        self.assertIsNotNone(plan.date_min)
        self.assertTrue(len(plan.plan_summary) > 0)
        self.assertTrue(plan.latency_ms < 50.0)

    def test_visual_query_decomposition(self) -> None:
        """Verify visual facet extraction for images, receipts, and signatures."""
        q = "Ảnh biên lai thuê nhà có chữ ký"
        plan = self.engine.decomposer.decompose(q, allow_slm=False)

        self.assertIn("visual", plan.active_facets)
        self.assertTrue(any(t in plan.visual_tags for t in ["receipt", "stamp"]))
        self.assertTrue(any(e in plan.extensions for e in [".jpg", ".png", ".jpeg", ".webp"]))

    def test_multi_way_rrf_fusion(self) -> None:
        """Verify multi-way reciprocal rank fusion combines orthogonal candidate streams."""
        lexical_stream = FacetResult(
            facet_name="lexical",
            candidates=[self.doc_telegram, self.doc_code],
            weight=1.0,
        )
        prov_stream = FacetResult(
            facet_name="provenance",
            candidates=[self.doc_telegram],
            weight=1.5,
        )

        fused = self.engine.multi_way_rrf.fuse([lexical_stream, prov_stream], top_k=5)
        self.assertTrue(len(fused) >= 2)
        # doc_telegram should be #1 because it matched both lexical and provenance streams
        top = fused[0]
        self.assertEqual(top["file_name"], "Bao_Cao_Q3_Telegram.pdf")
        self.assertIn("lexical", top["matched_facets"])
        self.assertIn("provenance", top["matched_facets"])
        self.assertTrue(top["rrf_score"] > fused[1]["rrf_score"])

    def test_sufficiency_evaluator_sufficient(self) -> None:
        """Verify evaluator returns SUFFICIENT when candidates adequately cover plan."""
        plan = RetrievalPlan(
            raw_query="Báo cáo Telegram",
            active_facets=["lexical", "provenance"],
            lexical_keywords=["báo", "cáo"],
            source_app="Telegram",
        )
        candidate = dict(self.doc_telegram)
        candidate["matched_facets"] = ["lexical", "provenance"]
        candidate["vector_similarity"] = 0.75
        candidate["rrf_score"] = 85.0

        report = self.engine.evaluator.evaluate(plan, [candidate])
        self.assertEqual(report.verdict, "SUFFICIENT")
        self.assertTrue(report.confidence >= 0.68)
        self.assertEqual(len(report.missing_facets), 0)

    def test_sufficiency_evaluator_insufficient(self) -> None:
        """Verify evaluator flags missing facets when candidate does not satisfy conditions."""
        plan = RetrievalPlan(
            raw_query="Báo cáo từ Telegram",
            active_facets=["lexical", "provenance", "temporal"],
            lexical_keywords=["báo", "cáo"],
            source_app="Telegram",
            date_min=time.time() - 3600,  # 1 hour ago
            date_max=time.time(),
        )
        # Provide candidate that is 10 days old and has no provenance
        cand_old = dict(self.doc_code)
        cand_old["matched_facets"] = ["lexical"]
        cand_old["vector_similarity"] = 0.20
        cand_old["rrf_score"] = 30.0

        report = self.engine.evaluator.evaluate(plan, [cand_old])
        self.assertIn(report.verdict, ["PARTIAL", "INSUFFICIENT"])
        self.assertTrue(len(report.missing_facets) > 0)
        self.assertIn("provenance", report.missing_facets)

    def test_corrective_retriever_actions(self) -> None:
        """Verify corrective retriever produces recovery actions for missing facets."""
        plan = RetrievalPlan(
            raw_query="Tìm biên lai hóa đơn",
            active_facets=["visual", "temporal"],
            visual_tags=["receipt"],
            date_min=time.time() - 86400,  # 1 day ago
            date_max=time.time(),
        )
        report = SufficiencyReport(
            confidence=0.35,
            verdict="INSUFFICIENT",
            missing_facets=["temporal", "visual"],
        )

        res = self.engine.corrector.correct(plan, report, current_candidates=[], iteration=1)
        self.assertTrue(len(res.actions) >= 1)
        action_types = [a.action_type for a in res.actions]
        self.assertTrue(any(t in action_types for t in ["widen_temporal", "ocr_visual_fallback"]))

    def test_reasoning_trace_construction(self) -> None:
        """Verify ReasoningTrace steps, serialization, and markdown formatting."""
        trace = ReasoningTrace(raw_query="Test Query")
        trace.add_step(
            phase="decompose",
            thought="Phân tích intent",
            action="decompose()",
            observation="Kích hoạt 2 facets",
            evaluation="Hợp lệ",
            latency_ms=2.5,
        )
        trace.finalize(confidence=0.85, is_sufficient=True)

        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.final_confidence, 0.85)
        self.assertTrue(trace.is_sufficient)

        d = trace.to_dict()
        self.assertEqual(d["raw_query"], "Test Query")
        self.assertEqual(len(d["steps"]), 1)

        md = trace.render_markdown()
        self.assertIn("FR-CoT Reasoning Trace", md)
        self.assertIn("Phân tích intent", md)

    def test_end_to_end_frcot_provenance_search(self) -> None:
        """Verify end-to-end FR-CoT search on provenance query with full trace."""
        res = self.engine.search("tìm file pdf báo cáo tải từ Telegram", limit=5)

        self.assertTrue(len(res["results"]) > 0)
        top_item = res["results"][0]
        self.assertEqual(top_item.file_name, "Bao_Cao_Q3_Telegram.pdf")

        # Verify FR-CoT Reasoning Trace is attached
        self.assertIn("reasoning_trace", res)
        trace: ReasoningTrace = res["reasoning_trace"]
        self.assertTrue(len(trace.steps) >= 4)

        # Check all key phases exist in trace
        phases = [s.phase for s in trace.steps]
        self.assertIn("decompose", phases)
        self.assertIn("retrieve", phases)
        self.assertIn("evaluate", phases)
        self.assertIn("rerank", phases)

        # Check sufficiency report
        self.assertIn("sufficiency_report", res)
        self.assertTrue(res["sufficiency_report"]["confidence"] > 0.6)

    def test_end_to_end_frcot_visual_search(self) -> None:
        """Verify end-to-end FR-CoT search on visual multimodal receipt query."""
        res = self.engine.search("ảnh biên lai có chữ ký", limit=5)

        self.assertTrue(len(res["results"]) > 0)
        top_item = res["results"][0]
        self.assertEqual(top_item.file_name, "Bien_Lai_Thue_Nha.jpg")
        self.assertIn("reasoning_trace", res)

    def test_multi_document_synthesis(self) -> None:
        """Verify Phase 6 multi-document synthesis cites multiple sources."""
        docs = [self.doc_telegram, self.doc_receipt]
        ans = qa_engine.synthesize_multi_document_answer(
            documents=docs,
            question="Cho biết doanh thu quý 3 và số tiền thuê nhà?",
            use_cloud_if_available=False
        )

        self.assertIsNotNone(ans)
        self.assertTrue(len(ans["sources"]) >= 2)
        answer_text = ans["answer"]
        self.assertTrue("Bao_Cao_Q3_Telegram.pdf" in answer_text or "Bien_Lai_Thue_Nha.jpg" in answer_text)


if __name__ == "__main__":
    unittest.main()
