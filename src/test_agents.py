from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens


def make_config(tmp_path: Path) -> LabConfig:
    """Khởi tạo một LabConfig cô lập cho môi trường test với state_dir nằm trong tmp_path."""
    base_cfg = load_config(Path(__file__).resolve().parent.parent)
    test_state = tmp_path / "state"
    test_state.mkdir(parents=True, exist_ok=True)
    (test_state / "profiles").mkdir(parents=True, exist_ok=True)

    return LabConfig(
        base_dir=base_cfg.base_dir,
        data_dir=base_cfg.data_dir,
        state_dir=test_state,
        compact_threshold_tokens=100,  # Ngưỡng thấp để dễ kích hoạt compaction trong test
        compact_keep_messages=2,
        model=base_cfg.model,
        judge_model=base_cfg.judge_model,
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Kiểm tra hoạt động CRUD của UserProfileStore trên User.md."""
    store_dir = tmp_path / "profiles"
    store = UserProfileStore(store_dir)
    user_id = "test_user"

    # 1. Kiểm tra read khi chưa có file (fallback default)
    initial_text = store.read_text(user_id)
    assert f"User Profile: {user_id}" in initial_text

    # 2. Kiểm tra write_text
    profile_content = f"# User Profile: {user_id}\n\n- **Name**: Test Person\n- **Location**: Da Nang\n"
    file_path = store.write_text(user_id, profile_content)
    assert file_path.is_file()
    assert store.file_size(user_id) > 0
    assert "Test Person" in store.read_text(user_id)

    # 3. Kiểm tra edit_text (thay đổi Da Nang thành Hue)
    changed = store.edit_text(user_id, "Da Nang", "Hue")
    assert changed is True
    assert "Hue" in store.read_text(user_id)
    assert "Da Nang" not in store.read_text(user_id)

    # 4. Kiểm tra helper upsert_fact & facts
    store.upsert_fact(user_id, "drink", "tra sua")
    facts = store.facts(user_id)
    assert facts.get("drink") == "tra sua"
    assert facts.get("name") == "Test Person"


def test_compact_trigger(tmp_path: Path) -> None:
    """Kiểm tra CompactMemoryManager tự động kích hoạt compact khi vượt ngưỡng token."""
    manager = CompactMemoryManager(threshold_tokens=50, keep_messages=2)
    thread_id = "thread_test_compact"

    # Append một số tin nhắn dài để vượt ngưỡng 50 tokens
    manager.append(thread_id, "user", "Tin nhắn thứ nhất: Đây là một đoạn văn bản tương đối dài nhằm mục đích tăng lượng token của thread lên.")
    manager.append(thread_id, "assistant", "Tin nhắn thứ hai: Phản hồi từ trợ lý ảo cũng có độ dài đáng kể để kiểm tra cơ chế compaction tự động.")
    manager.append(thread_id, "user", "Tin nhắn thứ ba: Một tin nhắn khác được đưa vào để chắc chắn vượt ngưỡng và số lượng message > keep_messages.")

    ctx = manager.context(thread_id)
    # Số lần compact phải >= 1
    assert manager.compaction_count(thread_id) >= 1
    # Số lượng messages còn lại trong list chỉ bằng keep_messages (2)
    assert len(ctx["messages"]) == 2
    # Bản tóm tắt summary phải được tạo ra và chứa nội dung đã nén
    summary_str = str(ctx["summary"])
    assert len(summary_str) > 0
    assert "user:" in summary_str or "Tin nhắn thứ nhất" in summary_str


def test_cross_session_recall(tmp_path: Path) -> None:
    """Kiểm tra: Advanced Agent nhớ facts qua session mới, trong khi Baseline Agent thì quên."""
    cfg = make_config(tmp_path)
    user_id = "cross_session_user"

    baseline = BaselineAgent(cfg, force_offline=True)
    advanced = AdvancedAgent(cfg, force_offline=True)

    # Session 1: Người dùng giới thiệu tên và sở thích
    s1 = "session_1"
    msg1 = "Chào bạn, mình tên là DũngCT. Đồ uống yêu thích của mình là cà phê sữa đá."
    baseline.reply(user_id=user_id, thread_id=s1, message=msg1)
    advanced.reply(user_id=user_id, thread_id=s1, message=msg1)

    # Session 2: Phiên mới hoàn toàn, hỏi lại thông tin
    s2 = "session_2"
    q = "Mình tên gì và đồ uống yêu thích là gì?"
    resp_baseline = baseline.reply(user_id=user_id, thread_id=s2, message=q)
    resp_advanced = advanced.reply(user_id=user_id, thread_id=s2, message=q)

    # Baseline không có persistent memory -> Quên sạch thông tin cũ
    ans_b = resp_baseline["answer"]
    assert "DũngCT" not in ans_b or "cà phê sữa đá" not in ans_b
    assert "chưa có thông tin" in ans_b.lower() or "mới" in ans_b.lower()

    # Advanced có User.md -> Nhớ chính xác cả Tên và Đồ uống yêu thích
    ans_a = resp_advanced["answer"]
    assert "DũngCT" in ans_a
    assert "cà phê sữa đá" in ans_a


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Kiểm tra: Compact memory giúp giảm tải lượng prompt tokens tích luỹ trên chuỗi hội thoại dài."""
    cfg = make_config(tmp_path)
    user_id = "stress_test_user"
    thread_id = "long_thread_test"

    baseline = BaselineAgent(cfg, force_offline=True)
    advanced = AdvancedAgent(cfg, force_offline=True)

    long_turns = [
        "Lượt 1: NASA Artemis III đang lên kế hoạch thử nghiệm các hệ thống hỗ trợ sự sống và tích hợp module trên quỹ đạo trước khi chính thức phóng.",
        "Lượt 2: Dự án máy bay siêu thanh X-59 đã đạt vận tốc Mach 1.1 nhằm nghiên cứu cách giảm chấn động âm thanh sonic boom.",
        "Lượt 3: Báo cáo khí hậu của WMO cảnh báo hiện tượng El Nino với xác suất vượt 80% trong các tháng tới.",
        "Lượt 4: Kế hoạch năng lượng British Columbia kết hợp việc mở rộng công suất nguồn điện và tối ưu hiệu quả sử dụng năng lượng.",
        "Lượt 5: Người dùng yêu cầu tóm tắt lại các nội dung kỹ thuật với văn phong ngắn gọn, nêu rõ trade-off hệ thống.",
        "Lượt 6: Bổ sung thêm thông tin về việc quản lý rủi ro và các mốc kiểm thử trong quy trình MLOps.",
    ]

    for turn in long_turns:
        baseline.reply(user_id=user_id, thread_id=thread_id, message=turn)
        advanced.reply(user_id=user_id, thread_id=thread_id, message=turn)

    # Baseline kéo theo toàn bộ lịch sử nguyên văn -> prompt_token_usage tích luỹ tăng nhanh
    prompt_baseline = baseline.prompt_token_usage(thread_id)
    # Advanced đã kích hoạt compact nén các message cũ
    prompt_advanced = advanced.prompt_token_usage(thread_id)
    compactions = advanced.compaction_count(thread_id)

    assert compactions > 0
    # Trên chuỗi hội thoại dài có compact, prompt load của Advanced thấp hơn hoặc tối ưu hơn đáng kể
    assert prompt_advanced < prompt_baseline


def test_confidence_threshold_and_noise_filtering() -> None:
    """[Bonus Test 99-100 Rubric]: Kiểm tra lọc nhiễu, câu đùa và ngưỡng tin cậy (Confidence Threshold)."""
    from memory_store import extract_profile_updates

    # 1. Câu hỏi thuần túy -> Không được trích xuất nhầm từ nghi vấn thành Tên
    res_question = extract_profile_updates("Bạn có biết tên mình là gì không?")
    assert "name" not in res_question

    # 2. Câu đùa ("product manager chỉ là câu đùa") -> Confidence thấp -> Bị loại bỏ
    res_joke = extract_profile_updates("Mình đùa với đồng nghiệp là hay chuyển sang product manager, nhưng thực ra không phải.")
    assert res_joke.get("profession") != "product manager"

    # 3. Chuyến đi ngắn ngày ("Hà Nội chỉ là nơi mình vừa bay ra họp hai ngày") -> Confidence < 0.7 -> Bị lọc
    res_trip = extract_profile_updates("Hà Nội chỉ là nơi mình vừa bay ra họp hai ngày thôi.")
    assert "hà nội" not in str(res_trip.get("location", "")).lower()

    # 4. Fact chuẩn xác với độ tin cậy cao (>= 0.7) -> Được chấp thuận
    res_valid = extract_profile_updates("Chào bạn, mình tên là DũngCT. Đồ uống yêu thích của mình là cà phê sữa đá.")
    assert res_valid.get("name") == "DũngCT"
    assert res_valid.get("favorite_drink") == "cà phê sữa đá"


def test_conflict_handling_and_memory_decay(tmp_path: Path) -> None:
    """[Bonus Test 99-100 Rubric]: Kiểm tra xử lý xung đột fact (Recency wins) và cơ chế Memory Decay."""
    store_dir = tmp_path / "profiles"
    store = UserProfileStore(store_dir)
    user_id = "test_conflict_user"

    # 1. Fact ban đầu: ở Huế, làm backend
    store.upsert_fact(user_id, "location", "Huế")
    store.upsert_fact(user_id, "profession", "backend engineer")
    store.upsert_fact(user_id, "temporary_project", "alpha_2026")
    assert store.facts(user_id)["location"] == "Huế"
    assert store.facts(user_id)["profession"] == "backend engineer"

    # 2. Người dùng đính chính: chuyển sang Đà Nẵng, làm MLOps -> Conflict handling ghi đè fact mới nhất
    store.upsert_fact(user_id, "location", "Đà Nẵng")
    store.upsert_fact(user_id, "profession", "MLOps engineer")
    current_facts = store.facts(user_id)
    assert current_facts["location"] == "Đà Nẵng"
    assert current_facts["profession"] == "MLOps engineer"
    assert "Huế" not in store.read_text(user_id)  # Không giữ đồng thời fact cũ sai

    # 3. Kích hoạt Memory Decay để dọn dẹp các facts tạm thời
    pruned = store.prune_decayed_facts(user_id)
    assert pruned == 1  # temporary_project bị dọn dẹp
    assert "temporary_project" not in store.facts(user_id)
    # Core facts vẫn nguyên vẹn
    assert store.facts(user_id)["location"] == "Đà Nẵng"
    assert store.facts(user_id)["profession"] == "MLOps engineer"

