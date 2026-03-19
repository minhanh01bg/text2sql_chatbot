# Text2SQL Chatbot

Đây là dự án Chatbot với chức năng cốt lõi (core) là **Text-to-SQL**, cho phép chuyển đổi ngôn ngữ tự nhiên thành câu lệnh truy vấn SQL để giao tiếp và tìm kiếm thông tin từ cơ sở dữ liệu. Dự án cung cấp hệ thống Backend AI mạnh mẽ và giao diện Frontend (demo) để người dùng có thể tương tác trực tiếp một cách dễ dàng.

## Các tính năng nổi bật (Features)

- ✅ **Core Text2SQL:** Chuyển đổi ngôn ngữ tự nhiên thành SQL query sử dụng sự kết hợp của LLMs (OpenAI), LangChain và LangGraph.
- ✅ **Backend API (FastAPI):** Hệ thống API hiệu suất cao và dễ dàng mở rộng, phục vụ giao tiếp với Frontend.
- ✅ **Frontend Demo:** Giao diện trực quan tích hợp sẵn để thử nghiệm luồng hỏi đáp (Chat) với Chatbot.
- ✅ **MongoDB Integration:** Lưu trữ Knowledge Base (cơ sở tri thức bổ sung), cấu trúc schema database và lịch sử/logs trò chuyện.
- ✅ **Logging & Tracking System:** Hệ thống lưu vết chi tiết hỗ trợ gỡ lỗi và phân tích chi phí:
  - Context câu trả lời và câu lệnh SQL sinh ra.
  - Thông tin token usage (số lượng token LLM đã tiêu thụ).

## Cấu trúc dự án

```text
text2sql_chatbot/
├── app/                     # Mã nguồn Backend (FastAPI, Text2SQL Core)
│   ├── api/                 # Các API endpoints (chat, langgraph, logs, ...)
│   ├── core/                # Core logic, config và xử lý trích xuất/embedding DB Schema
│   ├── models/              # Models cơ sở dữ liệu (MongoDB)
│   ├── schemas/             # Pydantic schemas (Data Validation)
│   └── services/            # Services xử lý AI, LangGraph workflows, log...
├── frontend/                # Mã nguồn Frontend (Giao diện Demo UI)
├── .env                     # File cấu hình biến môi trường
├── docker-compose.yml       # Môi trường chạy Docker (DB, Backend, Frontend...)
└── requirements.txt         # Các thư viện Python cần thiết cho Backend
```

## Cài đặt và Khởi chạy

### 1. Backend (AI & API)

1. **Cài đặt thư viện Python:**
```bash
pip install -r requirements.txt
```

2. **Cấu hình biến môi trường:**
Tạo file `.env` mẫu từ script có sẵn:
```bash
python create_env.py
```
Sau đó, mở file `.env` vừa được tạo và điền các thông tin cần thiết:
```env
OPENAI_API_KEY=your_openai_api_key_here
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=text2sql_db
# THÊM: Các biến kết nối Database cần Text2SQL (vd: MySQL, Postgres)
```

3. **Khởi chạy MongoDB:**
Đảm bảo bạn đã có MongoDB server đang chạy (local hoặc Docker).

4. **Khởi chạy Backend (FastAPI):**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Backend sẽ khởi chạy tại `http://localhost:8000`.

### 2. Frontend (Demo UI)

Giao diện để thử nghiệm Chatbot nằm ở thư mục `frontend`. Bạn di chuyển vào thư mục này, cài đặt dependencies (ví dụ `npm install` hoặc `yarn install`) và khởi động service theo hướng dẫn thực tế của ứng dụng frontend đang dùng.

*Lưu ý: Bạn cũng có thể dùng `docker-compose up` nếu dự án bạn đã thiết lập sẵn Docker compose nối cả Backend và Frontend lại.*

## Cấu hình Text2SQL (Embedding Database Schema)

Để AI chatbot có thể hiểu được Database của bạn và sinh ra các câu truy vấn SQL chuẩn xác, chúng ta cần đem cấu trúc SQL Database đi Embedding. Bạn phải chạy 2 bước sau **đúng thứ tự**:

### Bước 1: Trích xuất Schema từ SQL DB lưu vào MongoDB
Script này tự động quét và thu thập cấu trúc các bảng (tables, columns, primary/foreign keys) từ SQL DB của bạn sang MongoDB.
```bash
python -m app.core.extract_database_schema
```
👉 *Sau khi chạy xong, console sẽ in ra một **document ID**. Hãy COPY lại ID này để dùng ở bước sau.*

### Bước 2: Tạo Embeddings từ Schema MongoDB
Dùng ID lưu ở bước 1, script này sẽ gọi LLM tạo các vector embeddings biểu diễn ý nghĩa của các Table và lưu trữ lại vào MongoDB nhằm phục vụ quá trình RAG Text-to-SQL sau này.
```bash
python -m app.core.create_schema_embeddings --schema-doc-id <id_từ_bước_1>
```

## Toàn bộ Chức năng chính của Repo (Dashboard & Backend)

Hệ thống cung cấp một **Frontend Dashboard (Demo UI)** và các **Backend APIs** tương ứng để quản lý và sử dụng toàn bộ tính năng:

### 1. Chat / Intent (Tương tác AI)
- **Dashboard:** Giao diện Chat để người dùng gửi tin nhắn (dưới dạng ngôn ngữ tự nhiên) và nhận lại kết quả hoặc intent tương ứng. Tích hợp trực quan phản hồi từ `graph_service`.
- **Backend (`POST /api/v1/chat/` & `POST /api/v1/langgraph/`):** Xử lý tin nhắn đầu vào, sử dụng LangChain hoặc LangGraph để biến câu hỏi thành câu lượng truy vấn SQL (Text2SQL) và trả về dữ liệu.

### 2. Quản lý Sessions (Phiên trò chuyện)
- **Dashboard:** Xem danh sách phân trang tất cả các phiên trò chuyện (sessions) đã lưu trữ và xem chi tiết từng session.
- **Backend:** Các endpoints để tạo, theo dõi, và quản lý metadata của các cuộc gọi/chat session với AI.

### 3. API Logs (Theo dõi & Gỡ lỗi)
- **Dashboard:** Tra cứu lịch sử log chi tiết (theo ID, session, hoặc path endpoint) để debug nhanh. Có thể xem được chính xác mức độ tiêu hao tokens LLM (Token usage) và context đã dùng.
- **Backend (`GET /api/v1/logs/...`):** Cho phép truy xuất chi tiết lịch sử sinh câu trả lời, câu truy vấn SQL đã tạo, và chiết xuất chi phí từ câu gọi OpenAI.

### 4. Knowledge Base (Cơ sở Tri thức)
- **Dashboard:** Cho phép upload các tài liệu tĩnh (như file DOCX) làm Knowledge Base, theo dõi trạng thái tạo embeddings cho từng file và kiểm tra metadata nhằm truyền tải thêm các hướng dẫn nghiệp vụ chuyên sâu cho Chatbot.
- **Backend (`/api/v1/knowledge-base/`):** CRUD (Thêm/Sửa/Xóa/Tìm kiếm) các entry tri thức phụ trợ, giúp chatbot sinh ra câu trả lời chuẩn xác thay vì chỉ phụ thuộc vào Schema DB.

### 5. Schema DB (Tra cứu Cấu trúc CSCDL)
- **Dashboard:** Giao diện tra cứu (read-only) dành cho người quản trị để xem cấu trúc schema (tables, columns, properties) của Database hiện tại đã được trích xuất thành công để phục vụ truy vấn SQL.
- **Backend (Scripts Text2SQL):** Các endpoint và script chạy ngầm hỗ trợ trích xuất (Extract) Data Schema hiện tại sang JSON hoặc Embeddings để nhúng vào Prompt.

## Code ví dụ: Tương tác tự động với API Chat

```python
import requests

response = requests.post("http://localhost:8000/api/v1/chat/", json={
    "message": "Cho tôi xem biểu đồ số lượng học sinh theo ngành?",
    "use_knowledge_base": True
})

print(response.json())
```
