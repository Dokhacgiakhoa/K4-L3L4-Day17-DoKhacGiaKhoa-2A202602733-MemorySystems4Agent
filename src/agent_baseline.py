from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Agent A - Baseline: Chỉ có bộ nhớ ngắn hạn trong cùng thread_id.
    
    Không có User.md, không lưu persistent facts, bắt buộc quên khi sang thread mới.
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self.langchain_agent = None

        if not self.force_offline and self.config.model.api_key:
            try:
                self.langchain_agent = self._maybe_build_langchain_agent()
            except Exception:
                self.langchain_agent = None

    def _get_session(self, thread_id: str) -> SessionState:
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        return self.sessions[thread_id]

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Xử lý tin nhắn và trả về câu trả lời cùng số token sử dụng."""
        if not self.force_offline and self.langchain_agent is not None:
            try:
                from langchain_core.messages import HumanMessage
                session = self._get_session(thread_id)
                # Tính lượng prompt token tích luỹ
                prompt_text = "".join(m["content"] for m in session.messages) + message
                prompt_tokens = estimate_tokens(prompt_text)
                session.prompt_tokens_processed += prompt_tokens

                resp = self.langchain_agent.invoke(
                    {"messages": [HumanMessage(content=message)]},
                    config={"configurable": {"thread_id": thread_id}},
                )
                answer = resp["messages"][-1].content
                out_tokens = estimate_tokens(answer)
                session.token_usage += out_tokens
                session.messages.append({"role": "user", "content": message})
                session.messages.append({"role": "assistant", "content": answer})
                return {
                    "answer": answer,
                    "agent_tokens": out_tokens,
                    "prompt_tokens": prompt_tokens,
                }
            except Exception:
                pass

        return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        """Tổng token đầu ra do agent sinh ra trên thread này."""
        return self._get_session(thread_id).token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        """Tổng lượng token ngữ cảnh (prompt context) mà baseline đã kéo theo qua các lượt."""
        return self._get_session(thread_id).prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        """Baseline không có cơ chế compact memory."""
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Chế độ offline có thể lặp lại (deterministic) cho baseline.
        
        Quy tắc:
        - Tích luỹ toàn bộ lịch sử tin nhắn trong session hiện tại (ngữ cảnh tăng dần).
        - Nếu sang thread mới (lịch sử rỗng), baseline không biết gì về profile hay facts cũ.
        """
        session = self._get_session(thread_id)

        # Baseline giữ nguyên toàn bộ lịch sử tin nhắn cũ (cả user và assistant turns)
        # làm cho prompt context tăng nhanh theo hàm bậc hai O(N^2)
        history_parts = [f"[{m['role']}]: {m['content']}" for m in session.messages]
        prompt_text = "Conversation history:\n" + "\n".join(history_parts) + f"\nUser: {message}"
        prompt_tokens = estimate_tokens(prompt_text)
        session.prompt_tokens_processed += prompt_tokens

        # Thêm tin nhắn của user vào session
        session.messages.append({"role": "user", "content": message})

        # Xây dựng câu trả lời offline:
        # Nếu là thread mới (hoặc chỉ có 1 message vừa thêm), agent chưa có ngữ cảnh gì về người dùng
        # Baseline chỉ có thể trả lời nếu thông tin nằm ngay trong các message trước đó CÙNG THREAD.
        lower_msg = message.lower()
        if len(session.messages) <= 1:
            # Thread hoàn toàn mới -> Quên hết mọi facts ở thread khác!
            answer = "Chào bạn! Tôi là trợ lý AI. Vì đây là phiên trò chuyện mới nên tôi chưa có thông tin gì về bạn."
        else:
            # Có ngữ cảnh trong cùng thread: kiểm tra xem trong thread hiện tại có thông tin không
            all_thread_text = " ".join(m["content"] for m in session.messages)
            if "tên" in lower_msg:
                answer = "Trong cuộc trò chuyện này, tôi nhớ bạn đã trao đổi một số thông tin."
            else:
                answer = "Đã nhận thông tin từ bạn trong phiên làm việc này."

        out_tokens = estimate_tokens(answer)
        session.token_usage += out_tokens
        session.messages.append({"role": "assistant", "content": answer})

        return {
            "answer": answer,
            "agent_tokens": out_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _maybe_build_langchain_agent(self) -> Any:
        """Khởi tạo agent LangChain/LangGraph với InMemorySaver nếu có thư viện."""
        try:
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.prebuilt import create_react_agent

            model = build_chat_model(self.config.model)
            memory = MemorySaver()
            return create_react_agent(model, tools=[], checkpointer=memory)
        except Exception:
            return None
