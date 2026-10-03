from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Đọc dữ liệu benchmark conversations từ file JSON."""
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Dữ liệu trong {path} phải là một list")
        return data


def recall_points(answer: str, expected: list[str]) -> float:
    """Tính tỷ lệ recall facts (0.0 đến 1.0) xuất hiện trong câu trả lời."""
    if not expected:
        return 1.0
    ans_lower = answer.lower()
    matches = sum(1 for exp in expected if exp.lower() in ans_lower)
    return round(matches / len(expected), 2)


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Đánh giá chất lượng phản hồi heuristic:
    Kết hợp giữa điểm recall, tính ngắn gọn, và định dạng.
    """
    if not answer or "chưa có thông tin" in answer.lower():
        return 0.1
    recall = recall_points(answer, expected)
    # Khuyến khích câu trả lời súc tích, có cấu trúc
    length = len(answer)
    brevity_bonus = 0.2 if length < 300 else 0.0
    structure_bonus = 0.1 if ("-" in answer or "1." in answer) else 0.0
    score = (recall * 0.7) + brevity_bonus + structure_bonus
    return round(min(1.0, score), 2)


def run_agent_benchmark(agent_name: str, agent: Any, conversations: list[dict[str, Any]], config: Any) -> BenchmarkRow:
    """Đánh giá một agent trên bộ hội thoại:
    1. Cho agent xử lý toàn bộ turns theo từng conversation (mỗi conversation là 1 thread).
    2. Ghi nhận `agent tokens only` và `prompt tokens processed`.
    3. Đặt các câu hỏi recall ở một thread HOÀN TOÀN MỚI (cross-session).
    4. Tính điểm Recall trung bình và Quality trung bình.
    5. Đo lường tốc độ tăng dung lượng file User.md và số lần compaction.
    """
    total_agent_tokens = 0
    total_prompt_tokens = 0
    total_compactions = 0
    recall_scores: list[float] = []
    quality_scores: list[float] = []

    tested_users: set[str] = set()

    for conv in conversations:
        conv_id = conv.get("id", "conv-default")
        user_id = conv.get("user_id", "default_user")
        tested_users.add(user_id)
        turns = conv.get("turns", [])
        recall_questions = conv.get("recall_questions", [])

        # Luồng 1: Chạy các lượt hội thoại trong thread chính
        main_thread = f"{conv_id}_main"
        for turn in turns:
            res = agent.reply(user_id=user_id, thread_id=main_thread, message=turn)
            total_agent_tokens += res.get("agent_tokens", 0)
            total_prompt_tokens += res.get("prompt_tokens", 0)

        total_compactions += agent.compaction_count(main_thread)

        # Luồng 2: Kiểm tra recall ở thread MỚI (Cross-session check)
        for i, rq in enumerate(recall_questions):
            fresh_thread = f"{conv_id}_recall_thread_{i}"
            q_text = rq.get("question", "")
            expected = rq.get("expected_contains", [])
            resp = agent.reply(user_id=user_id, thread_id=fresh_thread, message=q_text)
            ans = resp.get("answer", "")
            
            # Ghi nhận token phát sinh trong recall
            total_agent_tokens += resp.get("agent_tokens", 0)
            total_prompt_tokens += resp.get("prompt_tokens", 0)

            rec = recall_points(ans, expected)
            qual = heuristic_quality(ans, expected)
            recall_scores.append(rec)
            quality_scores.append(qual)

    avg_recall = round(sum(recall_scores) / len(recall_scores), 2) if recall_scores else 0.0
    avg_quality = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0

    # Đo kích thước file memory (User.md)
    total_growth = 0
    if hasattr(agent, "memory_file_size"):
        total_growth = sum(agent.memory_file_size(u) for u in tested_users)

    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=total_growth,
        compactions=total_compactions,
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Định dạng kết quả bảng markdown so sánh giữa các agent."""
    headers = [
        "Agent",
        "Agent tokens only",
        "Prompt tokens processed",
        "Cross-session recall",
        "Response quality",
        "Memory growth (bytes)",
        "Compactions",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for r in rows:
        row_str = (
            f"| {r.agent_name} | {r.agent_tokens_only:,} | {r.prompt_tokens_processed:,} | "
            f"{r.recall_score * 100:.1f}% | {r.response_quality:.2f} | "
            f"{r.memory_growth_bytes:,} B | {r.compactions} |"
        )
        lines.append(row_str)
    return "\n".join(lines)


def main() -> None:
    """Thực thi cả Standard Benchmark và Long-Context Stress Benchmark."""
    config = load_config(Path(__file__).resolve().parent.parent)

    print("================================================================================")
    print("           MEMORY SYSTEMS BENCHMARK SUITE (Baseline vs Advanced)")
    print("================================================================================\n")

    # 1. Chạy Standard Benchmark (conversations.json)
    std_data_path = config.data_dir / "conversations.json"
    std_conversations = load_conversations(std_data_path)

    baseline_std = BaselineAgent(config, force_offline=True)
    advanced_std = AdvancedAgent(config, force_offline=True)

    row_b_std = run_agent_benchmark("Baseline Agent", baseline_std, std_conversations, config)
    row_a_std = run_agent_benchmark("Advanced Agent", advanced_std, std_conversations, config)

    print("### 1. Standard Benchmark (data/conversations.json - 10 conversations)")
    print(format_rows([row_b_std, row_a_std]))
    print("\n")

    # 2. Chạy Long-Context Stress Benchmark (advanced_long_context.json)
    stress_data_path = config.data_dir / "advanced_long_context.json"
    stress_conversations = load_conversations(stress_data_path)

    baseline_stress = BaselineAgent(config, force_offline=True)
    advanced_stress = AdvancedAgent(config, force_offline=True)

    row_b_stress = run_agent_benchmark("Baseline Agent", baseline_stress, stress_conversations, config)
    row_a_stress = run_agent_benchmark("Advanced Agent", advanced_stress, stress_conversations, config)

    print("### 2. Long-Context Stress Benchmark (data/advanced_long_context.json - 16 long turns)")
    print(format_rows([row_b_stress, row_a_stress]))
    print("\n================================================================================")


if __name__ == "__main__":
    main()
