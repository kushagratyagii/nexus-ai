# NEXUS AI Frontend

A Next.js interface for the existing NEXUS AI FastAPI backend.

## Requirements
- Node.js 20.9 or newer
- NEXUS FastAPI backend running at `http://127.0.0.1:8000`

## Setup (Windows PowerShell)
1. Extract this folder.
2. Open PowerShell in this folder.
3. Install dependencies:
   ```powershell
   npm install
   ```
4. Create `.env.local` from `.env.local.example`:
   ```powershell
   Copy-Item .env.local.example .env.local
   ```
5. Start the frontend:
   ```powershell
   npm run dev
   ```
6. Open http://localhost:3000

## Backend integration
The frontend uses:
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{thread_id}`
- `PATCH /api/conversations/{thread_id}`
- `DELETE /api/conversations/{thread_id}`
- `POST /api/chat`
- `POST /api/chat/resume`
- `POST /api/rag/upload`

Set `NEXT_PUBLIC_API_URL` in `.env.local` if the backend is hosted elsewhere.

## Notes
- Human approval is supported through the non-streaming `/api/chat` endpoint and `/api/chat/resume`.
- The current frontend deliberately uses `/api/chat` because it returns structured HITL interrupt data. Your existing `/api/chat/stream` endpoint is not yet wired into this interface.
- PDF upload currently indexes into the backend's configured FAISS knowledge base. It is not scoped to an individual conversation.
