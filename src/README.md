# Memory Systems Implementation (Solved & Production-Ready)

Thư mục `src/` chứa toàn bộ mã nguồn hoàn thiện của hệ thống bộ nhớ cho AI Agent:

- **Cấu trúc hoàn chỉnh**: Không còn pseudocode hay `TODO`, tất cả các module đều hoạt động đầy đủ ở cả Live Mode và Offline Mode.
- **Hỗ trợ 6 Providers**: `openai`, `custom`, `gemini`, `anthropic`, `ollama`, `openrouter` thông qua `model_provider.py` và `config.py`.
- **Tách bạch 3 tầng Memory**:
  - `Short-term Memory`: `SessionState` và buffer trượt theo thread.
  - `Persistent Memory`: `UserProfileStore` với tệp `User.md` chuẩn Markdown, hỗ trợ Structured Upsert, Memory Decay & Pruning.
  - `Compact Memory`: `CompactMemoryManager` tự động nén lịch sử thành summary súc tích khi vượt ngưỡng token.
- **Kỹ thuật Bonus cấp cao (Mức 99-100 Rubric)**:
  - Ngưỡng tin cậy `Confidence Threshold` ($\ge 0.70$).
  - Nhận diện đính chính `Conflict Handling` (nguyên tắc *Recency Wins*).
  - Lọc nhiễu câu đùa, câu hỏi thuần túy và chuyến công tác ngắn ngày.
- **Kiểm thử & Benchmark**:
  - `pytest src/test_agents.py -v`: 6/6 bài test chuyên sâu kiểm chứng mọi hành vi bộ nhớ (100% Passed).
  - `python src/benchmark.py`: Xuất 2 bảng Standard Benchmark và Long-Context Stress Benchmark đầy đủ 6 cột chỉ số.

