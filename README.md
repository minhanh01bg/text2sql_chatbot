# FastBase AI - Base Architecture với LangGraph, LangChain và FastAPI

Kiến trúc base cho ứng dụng AI sử dụng LangGraph, LangChain, FastAPI và MongoDB.

## Tính năng

- ✅ FastAPI làm API chính
- ✅ LangChain và LangGraph integration
- ✅ MongoDB với collections cho knowledge base và logs
- ✅ Logging system cho:
  - Knowledge base
  - Context câu trả lời
  - Token usage
- ✅ Environment configuration với .env

## Cấu trúc dự án

```
fast-base/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── chat.py          # Chat endpoints
│   │       ├── langgraph.py     # LangGraph endpoints
│   │       ├── knowledge_base.py # Knowledge base endpoints
│   │       └── logs.py          # Logs endpoints
│   ├── core/
│   │   ├── config.py            # Configuration
│   │   └── database.py          # MongoDB connection
│   ├── models/
│   │   ├── knowledge_base.py    # Knowledge base model
│   │   └── log.py               # Log model
│   ├── schemas/
│   │   ├── chat.py              # Chat schemas
│   │   ├── knowledge_base.py    # Knowledge base schemas
│   │   └── log.py               # Log schemas
│   ├── services/
│   │   ├── ai_service.py        # AI service (LangChain)
│   │   ├── langgraph_service.py # LangGraph workflow service
│   │   ├── chat_service.py      # Chat service
│   │   ├── knowledge_base_service.py # Knowledge base service
│   │   └── log_service.py       # Log service
│   └── main.py                  # FastAPI application
├── .env                         # Environment variables
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Cài đặt

1. **Cài đặt dependencies:**
```bash
pip install -r requirements.txt
```

2. **Tạo file .env:**
```bash
python create_env.py
```
Sau đó chỉnh sửa file `.env` với các giá trị của bạn:
```env
OPENAI_API_KEY=your_openai_api_key_here
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ai_base_db
```

3. **Chạy MongoDB:**
Đảm bảo MongoDB đang chạy trên máy của bạn hoặc cập nhật `MONGODB_URL` trong `.env`.

4. **Chạy ứng dụng:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Chat
- `POST /api/v1/chat/` - Gửi tin nhắn và nhận phản hồi từ AI (sử dụng LangChain)

### LangGraph
- `POST /api/v1/langgraph/` - Gửi tin nhắn và nhận phản hồi từ AI (sử dụng LangGraph workflow)

### Knowledge Base
- `POST /api/v1/knowledge-base/` - Tạo knowledge base entry
- `GET /api/v1/knowledge-base/` - Lấy tất cả knowledge base entries
- `GET /api/v1/knowledge-base/{id}` - Lấy knowledge base theo ID
- `GET /api/v1/knowledge-base/search/{query}` - Tìm kiếm knowledge base
- `DELETE /api/v1/knowledge-base/{id}` - Xóa knowledge base entry

### Logs
- `GET /api/v1/logs/` - Lấy tất cả logs
- `GET /api/v1/logs/{id}` - Lấy log theo ID
- `GET /api/v1/logs/session/{session_id}` - Lấy logs theo session ID

## Sử dụng

### Ví dụ: Chat với AI

```python
import requests

response = requests.post("http://localhost:8000/api/v1/chat/", json={
    "message": "What is artificial intelligence?",
    "use_knowledge_base": True
})

print(response.json())
```

### Ví dụ: Tạo Knowledge Base

```python
import requests

response = requests.post("http://localhost:8000/api/v1/knowledge-base/", json={
    "title": "AI Basics",
    "content": "Artificial Intelligence is the simulation of human intelligence...",
    "metadata": {"category": "education"}
})

print(response.json())
```

## Logging

Hệ thống tự động log:
- User queries
- AI responses
- Context của cuộc trò chuyện
- Token usage (prompt tokens, completion tokens, total tokens)
- Knowledge base references được sử dụng

Tất cả logs được lưu trong MongoDB collection `logs`.

## Development

Để phát triển thêm:
1. Thêm LangGraph workflows trong `app/services/`
2. Mở rộng knowledge base với vector search
3. Thêm authentication/authorization
4. Thêm rate limiting
5. Thêm monitoring và metrics

## License

MIT

