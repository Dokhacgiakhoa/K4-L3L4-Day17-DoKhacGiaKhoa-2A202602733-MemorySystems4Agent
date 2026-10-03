# TỔNG HỢP KIẾN THỨC CHUYÊN SÂU: MEMORY SYSTEMS FOR AI AGENTS
> **Khóa học**: AICB-P2T3 · Ngày 17 · Chương 4 — Agent Nâng Cao (VinUniversity, 2026)  
> **Tài liệu gốc**: `Memory_Systems_for_Agents.pdf` (73 trang)

---

## PHẦN 1: BẢN CHẤT VẤN ĐỀ — TẠI SAO AGENT "QUÊN"?

### 1.1. Stateless by Default
- Các LLM bản chất là **Stateless**: Mỗi API call là một request độc lập, không có trạng thái lưu giữ tự nhiên giữa các lần gọi.
- Người dùng nói "tôi thích Python" ở Session 1 $\rightarrow$ Session 2 (process mới) Agent bắt đầu từ con số 0.
- Khi hội thoại kéo dài ($>50$ turns) $\rightarrow$ Vượt ngưỡng giới hạn Context Window.

### 1.2. Analogy: Não người vs AI Agent
| Thành phần | Não người | AI Agent | Đặc tính kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Bộ nhớ làm việc** | Working Memory | **Context Window** | Nhanh, tạm thời, giới hạn token (RAM của agent), reset sau mỗi phiên. |
| **Bộ nhớ dài hạn** | Long-term Memory | **External Store** | Chậm hơn, bền vững, lưu trữ vô hạn (Redis, Postgres, Markdown, Vector DB). |

### 1.3. Nghịch lý Window 1M Tokens: Vì sao vẫn cần Memory?
Frontier models năm 2026 đã có Context Window lên tới 1M tokens, nhưng:
1. **Stateless**: Dù window lớn đến đâu, khi người dùng tắt trình duyệt / mở session mới, toàn bộ window vẫn bị reset.
2. **Context Rot & "Lost in the Middle"**: Khi đưa quá nhiều dữ liệu vào prompt, khả năng chú ý (attention) bị loãng. Thử nghiệm trên 18 model cho thấy accuracy giảm tới ~30% khi context bị kéo quá dài.
3. **Chi phí & Độ trễ (Latency)**: Xử lý full-context có p95 latency lên tới **17.1s** so với chỉ **1.4s** khi chỉ nạp memory chọn lọc.
> **Kết luận**: *Window lớn chỉ nới budget, không thay thế được Memory System. Bài toán cốt lõi là: Nạp gì, khi nào, và bao nhiêu.*

---

## PHẦN 2: CONTEXT ENGINEERING FRAMEWORK

### 2.1. Kiến trúc 7 Lớp Ngữ Cảnh (7 Context Layers)
Theo thứ tự ưu tiên từ ngoài vào trong:
1. **Policy Context (PIN - Không bao giờ cắt)**: Guardrails, safety rules, compliance.
2. **System Context (PIN - Không bao giờ cắt)**: Persona, role boundaries, instruction format.
3. **Task Context (Ưu tiên cao)**: Mục tiêu nhiệm vụ hiện tại.
4. **User Context**: Preferences ổn định, lịch sử user.
5. **Memory Context**: Recalled facts, relevant episodes.
6. **Retrieval Context**: RAG results, docs, dynamic retrieval.
7. **Tool Context (Cắt đầu tiên khi chạm limit)**: Function outputs cũ, raw payload đã xử lý xong.

### 2.2. Token Budget Heuristic
- **Short-term memory**: ~10%
- **Long-term facts**: ~4%
- **Episodic memory**: ~3%
- **Semantic knowledge**: ~3%
- **Tổng budget dành cho Memory**: $\approx 20\%$ Context Window (điểm xuất phát, kết hợp đặt trần tuyệt đối số token/lượt). Phần còn lại dành cho System Prompt, Task Instructions, Tool Results và Response Generation.

---

## PHẦN 3: COGNITIVE MEMORY MODEL — 4 LOẠI MEMORY CỦA AGENT

```
                   ┌─────────────────────────────────────────┐
                   │               AI AGENT                  │
                   └────────────────────┬────────────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│ 1. SHORT-TERM    │          │ 2. LONG-TERM     │          │ 3. EPISODIC      │
│ (Working Memory) │          │ (Declarative)    │          │ (Trải nghiệm cũ) │
├──────────────────┤          ├──────────────────┤          ├──────────────────┤
│ Context buffer,  │          │ Facts, profile,  │          │ Trajectory,      │
│ sliding window,  │          │ preferences bền  │          │ task outcomes,   │
│ session summary  │          │ vững (User.md)   │          │ reflections      │
└──────────────────┘          └──────────────────┘          └──────────────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │ 4. SEMANTIC      │
                              │ (Tri thức miền)  │
                              ├──────────────────┤
                              │ Vector DB,       │
                              │ Embeddings, RAG, │
                              │ Domain knowledge │
                              └──────────────────┘
```

1. **Short-term (Working Memory)**: Quản lý context window hiện tại bằng 3 chiến lược: Buffer thô $\rightarrow$ Summary Buffer $\rightarrow$ **Sliding Window + Summary** (Best practice cho production).
2. **Long-term (Declarative Memory)**: Lưu trữ facts, preferences qua nhiều phiên (Redis, PostgreSQL, hoặc file bền vững `User.md`).
3. **Episodic Memory**: Lưu lại lịch sử kinh nghiệm dưới dạng tuple `(task, trajectory, outcome, reflection)`. Giúp agent học được "lần trước cách X đã thất bại vì Y".
4. **Semantic Memory**: Lưu trữ và truy xuất tri thức miền tĩnh/động bằng Vector Database (Chroma, Pinecone, Qdrant).
*(Mở rộng: Procedural Memory - Lưu giữ "cách làm việc" dưới dạng `SKILL.md` hoặc Playbooks).*

---

## PHẦN 4: THIẾT KẾ PERSISTENCE, COMPACTION & BẢO MẬT (2025-2026)

### 4.1. Quy tắc Write-Back & Xử lý Xung đột Fact (Conflict Handling)
- **Hot path**: Trích xuất facts rõ ràng $\rightarrow$ ghi ngay vào persistent store.
- **Conflict Rule (Recency Wins & Bi-temporal)**: Khi người dùng đính chính (ví dụ: chuyển từ Huế sang Đà Nẵng):
  - Fact mới nhất sẽ đại diện cho hiện trạng (`Recency wins`).
  - Đánh dấu vô hiệu (`invalidate` / gắn `valid_to`) thay vì xóa trắng lịch sử cũ nếu cần audit.

### 4.2. Compaction Pipeline
Thay vì kéo toàn bộ lịch sử thô (khiến token tăng bậc hai $O(N^2)$ và gây context rot), pipeline compaction hoạt động:
1. **Detect Pressure**: Đo lường token count đạt ngưỡng `compact_threshold_tokens`.
2. **Summarize**: Tóm tắt decisions, blockers, bối cảnh chính của các lượt cũ.
3. **Extract Notes**: Đẩy facts quan trọng sang long-term storage (`User.md`).
4. **Rebuild Context**: Prompt mới chỉ gồm `User.md` + `Summary` + $K$ tin nhắn gần nhất (`keep_messages`).

### 4.3. File-Based Identity Control Plane & An toàn Bảo mật
- **File chuẩn hóa**: `AGENTS.md` (Workflow/Rules), `USER.md` (Thông tin người dùng bền vững), `MEMORY.md` (Nhật ký dài hạn), `SKILL.md` (Quy trình thực thi).
- **Phòng chống Memory Poisoning (OWASP ASI06)**:
  - Input bên ngoài (email, web, chat đùa) chỉ là **Data**, không được tự động biến thành **Instruction**.
  - Áp dụng whitelist trường được phép ghi, lọc nhiễu (Noise filtering) và đặt `confidence threshold`.

---

## PHẦN 5: ÁP DỤNG TRỰC TIẾP VÀO BÀI LAB DAY 17 CỦA CHÚNG TA

Dự án của chúng ta tại [K4-L3L4-Day17-DoKhacGiaKhoa-2A202602733-MemorySystems4Agent](file:///d:/Github/K4-L3L4-Day17-DoKhacGiaKhoa-2A202602733-MemorySystems4Agent) phản ánh chuẩn xác 100% các nguyên lý trong slide:

| Khái niệm trong Slide Bài giảng | Triển khai thực tế trong Codebase Lab | Kết quả đạt được trong Benchmark |
| :--- | :--- | :--- |
| **Stateless Baseline** | [src/agent_baseline.py](file:///d:/Github/K4-L3L4-Day17-DoKhacGiaKhoa-2A202602733-MemorySystems4Agent/src/agent_baseline.py): Chỉ lưu session trong RAM theo `thread_id`. | Cross-session recall chỉ đạt **0% - 4%** (quên sạch khi sang thread mới). |
| **Declarative Memory (`User.md`)** | [src/memory_store.py](file:///d:/Github/K4-L3L4-Day17-DoKhacGiaKhoa-2A202602733-MemorySystems4Agent/src/memory_store.py) (`UserProfileStore`): Lưu file Markdown bền vững `state/profiles/<user>/User.md`. | Cross-session recall đạt **100% tuyệt đối** qua mọi session. |
| **Compaction & Sliding Window** | [src/memory_store.py](file:///d:/Github/K4-L3L4-Day17-DoKhacGiaKhoa-2A202602733-MemorySystems4Agent/src/memory_store.py) (`CompactMemoryManager`): Tự động nén khi token $>600$, giữ lại $K=4$ tin nhắn gần nhất. | Trong Stress Test 16 turns dài: Tiết kiệm **66.4% prompt tokens** (từ 32,710 xuống còn 10,976 tokens). |
| **Conflict & Noise Filter** | [src/memory_store.py](file:///d:/Github/K4-L3L4-Day17-DoKhacGiaKhoa-2A202602733-MemorySystems4Agent/src/memory_store.py) (`extract_profile_updates`): Lọc đùa PM, bỏ qua họp 2 ngày ở Hà Nội, cập nhật Huế $\rightarrow$ Đà Nẵng. | Trả lời chính xác 100% câu hỏi bẫy nhiễu trong benchmark. |
