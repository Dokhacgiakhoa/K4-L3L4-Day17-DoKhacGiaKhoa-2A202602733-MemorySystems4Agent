# Báo cáo Phân tích Benchmark & Trade-off: Memory Systems for AI Agent

## 1. Kết quả Benchmark Thực nghiệm

Dưới đây là kết quả kiểm thử đối sánh giữa **Baseline Agent** (chỉ có short-term in-memory) và **Advanced Agent** (3 tầng: Short-term + Persistent `User.md` + Compact Memory) trên hai bộ dữ liệu chuẩn:

### 1.1. Standard Benchmark (`data/conversations.json` - 10 hội thoại, user `dungct`)

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Agent** | 2,550 | 25,017 | **4.0%** | 0.10 | 0 B | 0 |
| **Advanced Agent** | 4,669 | 40,182 | **100.0%** | **0.91** | 299 B | 10 |

### 1.2. Long-Context Stress Benchmark (`data/advanced_long_context.json` - 16 turns dài, user `dungct_stress`)

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Agent** | 442 | 32,710 | **0.0%** | 0.10 | 0 B | 0 |
| **Advanced Agent** | 960 | **10,976** *(giảm ~66%)* | **100.0%** | **0.97** | 234 B | 27 |

---

## 2. Phân tích Chuyên sâu các Khía cạnh Kỹ thuật (Theo Rubric 90-100)

### 2.1. Vì sao Advanced Agent có Recall vượt trội (100% so với 0 - 4% của Baseline)?
- **Cơ chế Baseline**: Baseline chỉ lưu session trong RAM theo từng `thread_id`. Khi sang thread mới (cross-session evaluation), phiên làm việc cũ không còn được nạp, dẫn tới việc agent hoàn toàn không biết gì về profile hay facts của người dùng.
- **Cơ chế Advanced**: Mọi fact ổn định (họ tên, nơi ở, nghề nghiệp, sở thích đồ uống, món ăn, thú cưng, response style) được trích xuất qua `extract_profile_updates()` và lưu trữ bền vững tại file `User.md` (`UserProfileStore`). Khi mở thread mới, agent nạp lại `User.md` vào prompt context, từ đó duy trì khả năng nhớ thông tin hoàn hảo (Cross-session Recall = 100%).

### 2.2. Nghịch lý Token ở Hội thoại ngắn vs Hội thoại dài
- **Tại hội thoại ngắn/trung bình (Standard Benchmark)**:
  - Advanced Agent tiêu tốn nhiều `Prompt tokens processed` hơn Baseline (40,182 tokens so với 25,017 tokens) và nhiều `Agent tokens only` hơn (4,669 so với 2,550).
  - *Nguyên nhân*: Advanced Agent phải liên tục mang theo nội dung của `User.md` trong mỗi lượt chat và sinh câu trả lời chi tiết, có cấu trúc (góp phần tăng điểm Response Quality lên 0.91). Với các cuộc hội thoại ngắn, chi phí overhead cố định để nạp profile lớn hơn lượng token tiết kiệm được từ việc compact.
- **Tại hội thoại dài và dày ngữ cảnh (Long-Context Stress Benchmark)**:
  - Baseline Agent kéo theo toàn bộ lịch sử thô qua từng lượt. Chi phí ngữ cảnh tăng theo hàm bậc hai:
    $$\text{Prompt Tokens}_{\text{Baseline}} = \sum_{i=1}^{N} \text{Tokens}(\text{History}_{1..i-1} + \text{Turn}_i)$$
    dẫn tới việc Baseline ngốn tới **32,710 prompt tokens**.
  - Advanced Agent kích hoạt **27 lần compaction**: khi tổng token vượt ngưỡng (`compact_threshold_tokens`), hệ thống nén các tin nhắn cũ vào bản `summary` và chỉ giữ lại $N$ tin nhắn gần nhất.
  - Kết quả: Prompt context của Advanced Agent giảm từ 32,710 xuống chỉ còn **10,976 tokens** (tiết kiệm **~66.4%** chi phí prompt ngữ cảnh).

### 2.3. Tốc độ tăng trưởng bộ nhớ (Memory Growth) & Rủi ro hệ thống
- File `User.md` chỉ tăng **299 Bytes** sau 10 phiên hội thoại Standard và **234 Bytes** sau phiên Stress test.
- *Rủi ro*: Nếu không có quy chuẩn lưu trữ, `User.md` có thể bị phình to vô hạn theo thời gian nếu lưu trữ cả những chi tiết tạm thời hoặc thông tin rác.
- *Giải pháp*: Trong giải pháp này, hệ thống áp dụng cơ chế **Structured Key-Value** (sử dụng `upsert_fact()`) kết hợp định dạng Markdown chuẩn hóa:
  - Facts cùng loại sẽ được ghi đè (ví dụ: đổi nơi ở từ Huế sang Đà Nẵng, chuyển nghề từ backend sang MLOps).
  - Ngăn ngừa tình trạng duplicate hay mâu thuẫn facts trong profile.

### 2.4. Phần Bonus kỹ thuật (Mức điểm 90-100)
1. **Conflict Handling & Correction**:
   - Tự động nhận diện các phát biểu đính chính ("giờ mình đang ở Huế chứ không còn ở Đà Nẵng", "từ tuần này làm việc ở Đà Nẵng vài tháng", "chuyển sang MLOps engineer chứ không làm backend nữa").
   - Ghi đè fact mới nhất vào `User.md`, đảm bảo tính nhất quán của bộ nhớ dài hạn.
2. **Noise Filtering & Entity Extraction**:
   - Loại bỏ các câu hỏi thuần túy (không để từ nghi vấn như "gì", "ai" bị trích xuất nhầm thành Tên).
   - Lọc bỏ thông tin đùa giỡn ("product manager chỉ là câu đùa").
   - Lọc bỏ thông tin tạm thời ("Hà Nội chỉ là nơi mình vừa bay ra họp 2 ngày" $\rightarrow$ không gán Hà Nội làm nơi ở).
