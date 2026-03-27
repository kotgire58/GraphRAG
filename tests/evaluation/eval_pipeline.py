"""
Module: eval_pipeline.py
Purpose: Evaluate Vector RAG vs Graph RAG using DeepEval.
Run: python -m tests.evaluation.eval_pipeline

Parallelism: concurrent test cases (semaphore), parallel vector+graph queries,
parallel judge metrics per mode. Checkpoints results.json under a lock.

Env: EVAL_MAX_CONCURRENT_CASES (default 4), EVAL_API_BASE, EVAL_JUDGE_MODEL.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

API_BASE = os.getenv("EVAL_API_BASE", "http://127.0.0.1:8058")
TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_PATH = Path(__file__).parent / "results.json"

MAX_CONCURRENT_CASES = max(
    1, int(os.getenv("EVAL_MAX_CONCURRENT_CASES", "4"))
)

# Same margin as print_results_table winner column (|score diff| <= tie)
EVAL_WINNER_MARGIN = float(os.getenv("EVAL_WINNER_MARGIN", "0.05"))

METRIC_NAMES_FOR_WINNER = [
    "AnswerRelevancyMetric",
    "FaithfulnessMetric",
    "ContextualRecallMetric",
    "ContextualPrecisionMetric",
]


def compute_winner_summary(
    results: list[dict | None],
    margin: float | None = None,
) -> dict:
    """Count vector vs graph wins per metric comparison (matches print table)."""
    m = EVAL_WINNER_MARGIN if margin is None else margin
    vector_wins = 0
    graph_wins = 0
    ties = 0
    skipped = 0
    for r in results:
        if r is None:
            continue
        vs_all = r.get("vector", {}).get("scores") or {}
        gs_all = r.get("graph", {}).get("scores") or {}
        for name in METRIC_NAMES_FOR_WINNER:
            v = vs_all.get(name)
            g = gs_all.get(name)
            if v is None or g is None:
                skipped += 1
                continue
            if g > v + m:
                graph_wins += 1
            elif v > g + m:
                vector_wins += 1
            else:
                ties += 1
    total = vector_wins + graph_wins + ties
    return {
        "margin": m,
        "vector_wins": vector_wins,
        "graph_wins": graph_wins,
        "ties": ties,
        "skipped_missing_scores": skipped,
        "total_metric_comparisons": total,
    }


def _bridge_openai_env() -> None:
    """Map GraphRAG .env LLM_* vars to DeepEval's OpenAI-compatible client."""
    if not os.getenv("OPENAI_API_KEY") and os.getenv("LLM_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.getenv("LLM_API_KEY", "")
    if not os.getenv("OPENAI_BASE_URL") and os.getenv("LLM_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = os.getenv("LLM_BASE_URL", "")


_bridge_openai_env()


def _judge_model() -> str:
    return os.getenv("EVAL_JUDGE_MODEL") or os.getenv(
        "LLM_CHOICE", "gpt-4o-mini"
    )


def _make_metrics(judge_model: str) -> list:
    """Fresh metric instances (avoid score bleed between runs)."""
    common = {
        "threshold": 0.5,
        "model": judge_model,
        "async_mode": False,
        "verbose_mode": False,
        "include_reason": False,
    }
    return [
        AnswerRelevancyMetric(**common),
        FaithfulnessMetric(**common),
        ContextualRecallMetric(**common),
        ContextualPrecisionMetric(**common),
    ]


def _measure_single_metric(
    metric, test: LLMTestCase
) -> tuple[str, float | None, str | None]:
    """Sync: run one metric; return (name, score, error_str)."""
    name = metric.__class__.__name__
    try:
        metric.measure(test)
        score = (
            round(float(metric.score), 3)
            if metric.score is not None
            else None
        )
        return name, score, None
    except Exception as e:
        logger.exception("Metric %s failed", name)
        return name, None, f"{name}: {e}"


async def _score_test_case_metrics_parallel(
    test: LLMTestCase,
    judge_model: str,
) -> tuple[dict[str, float | None], list[str]]:
    """Run four metrics in parallel (thread offload for sync measure())."""
    metrics = _make_metrics(judge_model)
    tasks = [
        asyncio.to_thread(_measure_single_metric, m, test) for m in metrics
    ]
    outcomes = await asyncio.gather(*tasks)
    scores: dict[str, float | None] = {}
    errors: list[str] = []
    for name, score, err in outcomes:
        scores[name] = score
        if err:
            errors.append(err)
    return scores, errors


async def query_rag(
    question: str,
    mode: str,
    client: httpx.AsyncClient,
) -> tuple[str, list[str]]:
    """Query the RAG API and return answer + retrieval context strings."""
    response = await client.post(
        f"{API_BASE}/chat",
        json={"message": question, "mode": mode},
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()

    answer = data.get("answer", "")

    context: list[str] = []
    for s in data.get("sources", []):
        if isinstance(s, dict):
            if s.get("content"):
                context.append(str(s["content"]))
            elif s.get("fact"):
                context.append(str(s["fact"]))
            elif s.get("text"):
                context.append(str(s["text"]))

    if not context and data.get("traversal_path"):
        tp = data["traversal_path"]
        if isinstance(tp, list):
            context = [str(x) for x in tp]
        else:
            context = [str(tp)]

    return answer, context


async def evaluate_test_case(
    case_index: int,
    test_case: dict,
    client: httpx.AsyncClient,
    judge_model: str,
) -> dict:
    """Run one test case: parallel queries, parallel judge metrics."""
    question = test_case["question"]
    ground_truth = test_case["ground_truth"]
    category = test_case["category"]

    print(f"\n[{case_index + 1}] Evaluating: {question[:55]}...")

    query_errors: list[str] = []

    v_task = asyncio.create_task(
        query_rag(question, "vector", client)
    )
    g_task = asyncio.create_task(
        query_rag(question, "graph", client)
    )
    v_out, g_out = await asyncio.gather(
        v_task, g_task, return_exceptions=True
    )

    if isinstance(v_out, BaseException):
        logger.exception("Vector query failed")
        vector_answer = f"ERROR: {v_out}"
        vector_context: list[str] = []
        query_errors.append(f"vector_query: {v_out}")
    else:
        vector_answer, vector_context = v_out

    if isinstance(g_out, BaseException):
        logger.exception("Graph query failed")
        graph_answer = f"ERROR: {g_out}"
        graph_context: list[str] = []
        query_errors.append(f"graph_query: {g_out}")
    else:
        graph_answer, graph_context = g_out

    fallback_ctx = ["No context retrieved"]

    vector_test = LLMTestCase(
        input=question,
        actual_output=vector_answer,
        expected_output=ground_truth,
        retrieval_context=vector_context if vector_context else fallback_ctx,
    )

    graph_test = LLMTestCase(
        input=question,
        actual_output=graph_answer,
        expected_output=ground_truth,
        retrieval_context=graph_context if graph_context else fallback_ctx,
    )

    (
        vector_scores,
        vector_metric_errors,
    ), (
        graph_scores,
        graph_metric_errors,
    ) = await asyncio.gather(
        _score_test_case_metrics_parallel(vector_test, judge_model),
        _score_test_case_metrics_parallel(graph_test, judge_model),
    )

    return {
        "case_index": case_index,
        "question": question,
        "category": category,
        "requires_hops": test_case.get("requires_hops", 1),
        "vector": {
            "answer": vector_answer[:200],
            "scores": vector_scores,
        },
        "graph": {
            "answer": graph_answer[:200],
            "scores": graph_scores,
        },
        "errors": (
            query_errors + vector_metric_errors + graph_metric_errors
        ),
    }


def print_results_table(results: list[dict]) -> None:
    """Print a formatted comparison table."""
    print("\n" + "=" * 80)
    print("VECTOR RAG vs GRAPH RAG — EVALUATION RESULTS")
    print("=" * 80)

    metrics = METRIC_NAMES_FOR_WINNER

    metric_short = {
        "AnswerRelevancyMetric": "Relevancy",
        "FaithfulnessMetric": "Faithfulness",
        "ContextualRecallMetric": "Recall",
        "ContextualPrecisionMetric": "Precision",
    }

    print(
        f"\n{'Question':<35} {'Hops':<5} "
        f"{'Metric':<14} {'Vector':>8} {'Graph':>8} {'Winner':>8}"
    )
    print("-" * 80)

    vector_wins = 0
    graph_wins = 0

    for result in results:
        q = result["question"][:33] + ".."
        hops = result["requires_hops"]

        for metric in metrics:
            v_score = result["vector"]["scores"].get(metric)
            g_score = result["graph"]["scores"].get(metric)

            v_str = f"{v_score:.3f}" if v_score is not None else "N/A"
            g_str = f"{g_score:.3f}" if g_score is not None else "N/A"

            if v_score is not None and g_score is not None:
                if g_score > v_score + EVAL_WINNER_MARGIN:
                    winner = "GRAPH ✓"
                    graph_wins += 1
                elif v_score > g_score + EVAL_WINNER_MARGIN:
                    winner = "VECTOR ✓"
                    vector_wins += 1
                else:
                    winner = "TIE"
            else:
                winner = "-"

            print(
                f"{q:<35} {hops:<5} "
                f"{metric_short[metric]:<14} "
                f"{v_str:>8} {g_str:>8} {winner:>8}"
            )

        print("-" * 80)

    print(
        f"\nOVERALL: Graph wins {graph_wins} | "
        f"Vector wins {vector_wins}"
    )

    print("\nBy hop depth:")
    for hop in sorted({r["requires_hops"] for r in results}):
        hop_results = [r for r in results if r["requires_hops"] == hop]

        graph_avg: list[float] = []
        vector_avg: list[float] = []

        for r in hop_results:
            for m in metrics:
                gs = r["graph"]["scores"].get(m)
                vs = r["vector"]["scores"].get(m)
                if gs is not None:
                    graph_avg.append(gs)
                if vs is not None:
                    vector_avg.append(vs)

        g_mean = sum(graph_avg) / len(graph_avg) if graph_avg else 0.0
        v_mean = sum(vector_avg) / len(vector_avg) if vector_avg else 0.0

        print(
            f"  {hop}-hop queries: "
            f"Graph avg {g_mean:.3f} | "
            f"Vector avg {v_mean:.3f}"
        )

    print("=" * 80)


def _collect_errors_from_slots(slots: list[dict | None]) -> list[str]:
    out: list[str] = []
    for r in slots:
        if r:
            out.extend(r.get("errors", []))
    return out


def write_results_snapshot(
    *,
    test_cases: list,
    results_slots: list[dict | None],
    judge_model: str,
    in_progress: bool,
    max_concurrent: int,
) -> None:
    """Write results.json (full overwrite)."""
    completed = sum(1 for r in results_slots if r is not None)
    out: dict = {
        "timestamp": datetime.now().isoformat(),
        "total_planned": len(test_cases),
        "completed_cases": completed,
        "in_progress": in_progress,
        "max_concurrent_cases": max_concurrent,
        "api_base": API_BASE,
        "judge_model": judge_model,
        "results": results_slots,
        "collected_errors": _collect_errors_from_slots(results_slots),
    }
    if completed > 0:
        out["winner_summary"] = compute_winner_summary(results_slots)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        test_cases = json.load(f)

    judge_model = _judge_model()
    n = len(test_cases)
    print(f"Running evaluation on {n} test cases...")
    print(
        f"Parallel: up to {MAX_CONCURRENT_CASES} cases at once; "
        "vector||graph queries; 4+4 judge metrics in parallel."
    )
    print(f"Judge model: {judge_model}")

    results_slots: list[dict | None] = [None] * n
    snapshot_lock = asyncio.Lock()

    limits = httpx.Limits(
        max_keepalive_connections=50,
        max_connections=100,
    )

    async with httpx.AsyncClient(limits=limits, timeout=120.0) as client:
        try:
            health = await client.get(f"{API_BASE}/health", timeout=10.0)
            print(f"API health: {health.json()}")
        except Exception as e:
            print(f"API not reachable at {API_BASE}: {e}")
            return

        sem = asyncio.Semaphore(MAX_CONCURRENT_CASES)

        async def run_bounded(idx: int, tc: dict) -> None:
            async with sem:
                try:
                    result = await evaluate_test_case(
                        idx, tc, client, judge_model
                    )
                except Exception as e:
                    logger.exception("Case %s failed", idx)
                    result = {
                        "case_index": idx,
                        "question": tc.get("question", ""),
                        "category": tc.get("category", ""),
                        "requires_hops": tc.get("requires_hops", 1),
                        "vector": {"answer": "", "scores": {}},
                        "graph": {"answer": "", "scores": {}},
                        "errors": [f"evaluate_test_case: {e}"],
                    }
                async with snapshot_lock:
                    results_slots[idx] = result
                    write_results_snapshot(
                        test_cases=test_cases,
                        results_slots=results_slots,
                        judge_model=judge_model,
                        in_progress=True,
                        max_concurrent=MAX_CONCURRENT_CASES,
                    )
                done = sum(1 for r in results_slots if r is not None)
                print(
                    f"  Checkpoint {done}/{n} -> {RESULTS_PATH.name} "
                    f"(in_progress=true)"
                )

        await asyncio.gather(
            *[run_bounded(i, tc) for i, tc in enumerate(test_cases)]
        )

    write_results_snapshot(
        test_cases=test_cases,
        results_slots=results_slots,
        judge_model=judge_model,
        in_progress=False,
        max_concurrent=MAX_CONCURRENT_CASES,
    )

    final_results = [r for r in results_slots if r is not None]
    print(f"\nFull results saved to {RESULTS_PATH}")
    all_errors = _collect_errors_from_slots(results_slots)
    if all_errors:
        print(f"\nErrors/warnings collected: {len(all_errors)}")
        for err in all_errors[:30]:
            print(f"  - {err}")
        if len(all_errors) > 30:
            print(
                f"  ... and {len(all_errors) - 30} more "
                "(see results JSON)"
            )

    print_results_table(final_results)


if __name__ == "__main__":
    asyncio.run(main())
