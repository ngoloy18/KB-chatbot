# Week 6 Presentation Plan

## Goal

Prepare a 15-minute Week 6 demo for the KB Chat Bot Dev AI server.

The Week 6 spec asks for:

- Simple UI demo
- Manual verification
- README/setup confidence
- 15-minute presentation
- English answers with source citations
- Clear explanation of architecture
- Honest limitations and next steps

Important correction: the HTML spec says to explain "Long-Context instead of Embeddings", but the current server uses embeddings, pgvector, and RAG retrieval. In the presentation, explain the real system:

> The original plan mentioned long-context retrieval, but the implemented server uses chunking plus embeddings because it scales better as documents grow. New uploads are automatically chunked, embedded, stored, and then retrieved with semantic search plus keyword/ranking fallback.

## 15-Minute Timing

| Time | Section | What to show |
| --- | --- | --- |
| 0:00-2:00 | Product intro | What the app is, why it exists, who uses it |
| 2:00-4:00 | Architecture | React UI, FastAPI, PostgreSQL, pgvector, Gemini |
| 4:00-6:00 | Upload flow | User uploads markdown, server chunks and embeds automatically |
| 6:00-10:00 | Chat demo | Ask 3-4 questions, show answers and sources |
| 10:00-11:00 | Edge case | Ask outside-docs question, show refusal to hallucinate |
| 11:00-13:00 | Security and database | JWT, refresh tokens, user isolation, source citations |
| 13:00-15:00 | Limitations and next steps | Critical thinking, improvements, close |

## Slide Outline

### Slide 1: Title

Claim: "KB Chat Bot Dev AI turns internal engineering docs into a searchable, cited assistant."

Talking points:

- This is a developer knowledge-base chatbot.
- Users ask engineering questions in the UI.
- The server answers in English using uploaded documentation.
- Every answer returns source documents so the answer can be checked.

### Slide 2: Why We Built It

Claim: "Engineering knowledge is useful only when people can find the right rule quickly."

Talking points:

- Team rules are spread across API standards, database standards, logging standards, PR guidelines, Git flow docs, and coding conventions.
- Search alone is weak because users may not know the exact wording.
- The chatbot gives a faster path: ask naturally, get a cited answer.
- It is not meant to replace documentation; it is a safer front door to the docs.

### Slide 3: What Works Now

Claim: "The server supports the full demo loop: auth, upload, retrieval, answer, sources, and history."

Show or say:

- Login and JWT auth
- Authenticated markdown document upload
- Automatic chunking and embeddings
- Semantic retrieval with pgvector
- Gemini answer generation
- Source citations
- Chat sessions and history
- User-scoped permissions

### Slide 4: Tech Stack

Claim: "The stack is intentionally simple: one FastAPI backend, one React frontend, one PostgreSQL database."

Backend:

- FastAPI
- Pydantic
- SQLAlchemy async
- Alembic migrations
- PostgreSQL
- pgvector
- JWT auth
- Gemini API

Frontend:

- React
- Vite
- React Router
- Tailwind CSS
- Fetch API client

Storage:

- PostgreSQL schema `kb`
- Local markdown upload folder
- Embeddings stored in `document_chunks`
- Optional pgvector `embedding_vector` column for fast vector search

### Slide 5: Server Architecture

Claim: "The backend keeps clean boundaries between HTTP, business logic, and database queries."

Flow:

```text
React/Vite UI
  -> FastAPI routes
  -> dependencies and middleware
  -> services
  -> repositories
  -> PostgreSQL / uploads / Gemini
```

Explain:

- Routes handle HTTP inputs, auth dependencies, files, and status codes.
- Services hold business rules.
- Repositories own SQLAlchemy queries and commits.
- Models map the PostgreSQL `kb` schema.
- AI providers are wrapped behind service classes so Gemini can be swapped later.

### Slide 6: Document Upload And Embedding Flow

Claim: "New documents become searchable immediately after upload."

Flow:

```text
User uploads .md file
  -> validate file type and size
  -> save local file
  -> create document row
  -> split text into chunks
  -> call Gemini embedding model
  -> store chunk embeddings
  -> sync pgvector embedding_vector
  -> create document version snapshot
```

What to emphasize:

- Normal users own their uploads, and admins can see every document.
- Only markdown is accepted right now.
- Duplicate content is checked by checksum.
- The server automatically chunks and embeds during create/update.
- The chat endpoint can retrieve the uploaded document right away.

### Slide 7: Chat/RAG Flow

Claim: "Chat answers are grounded in retrieved chunks, not free-form model memory."

Flow:

```text
User asks question
  -> authenticate user
  -> embed the question
  -> search readable document chunks
  -> merge vector + keyword candidates
  -> generic ranking prefers relevant standards/policies over examples
  -> build prompt with retrieved context
  -> Gemini writes answer in English
  -> save user message, assistant message, sources, AI run
  -> return answer + source names
```

Say this clearly:

> The model does not get every document blindly. The server retrieves the most relevant chunks first, then Gemini answers only from that context.

### Slide 8: Database Design

Claim: "The schema supports auth, documents, permissions, chat history, citations, and auditability."

Main groups:

- Auth: `users`, refresh tokens, verification/reset tokens
- Documents: `document_categories`, `documents`, `document_chunks`, `document_versions`
- Permissions: `document_permissions`
- Chat: `chat_sessions`, `chat_messages`, `message_sources`, `ai_runs`
- Audit: `audit_logs`

Key relationships:

- One user has many chat sessions.
- One chat session has many messages.
- Assistant messages link to source chunks through `message_sources`.
- One document has many chunks and versions.
- Permissions decide which users can read/write/own a document.

### Slide 9: Security And Isolation

Claim: "The app protects user data and document access."

What is implemented:

- JWT access tokens
- Refresh token table for revocable sessions
- Admin and normal user roles
- Document permissions: `read`, `write`, `owner`
- Chat sessions scoped by `current_user.id`
- User-owned document uploads
- Rate limiting for sensitive auth/upload endpoints
- Audit logging for important actions

Demo proof:

- Normal user can only see sessions they own.
- Normal user can retrieve documents they uploaded or have permission to read.
- Admin can manage document permissions.

### Slide 10: Live Demo Script

Claim: "The product works end to end."

Demo order:

1. Open the React UI.
2. Login as admin.
3. Show documents page.
4. Upload a small markdown demo document.
5. Ask a question about that new document.
6. Show the answer and source citation.
7. Ask 3 existing KB questions.
8. Open session history.
9. Ask an out-of-docs question.

Recommended demo questions:

```text
What HTTP method should be used to retrieve resources?
```

Expected: `GET`, source should be API Standard.

```text
When should I use POST instead of PUT?
```

Expected: POST creates resources or non-idempotent operations; PUT replaces a resource when full replacement is supported.

```text
What should a pull request description include before review?
```

Expected: PR guideline answer with PR source.

```text
What is the required structured log format and which fields are mandatory?
```

Expected: logging standard answer with logging source.

```text
How do I set up a Kubernetes cluster?
```

Expected:

```text
This information is not available in the current documents.
```

### Slide 11: Critical Thinking

Claim: "The current server is demo-ready, but the next version should improve reliability and production readiness."

Limitations:

- Uploads are markdown-only.
- Files are stored locally, not in object storage.
- Gemini is an external dependency, so availability, latency, and cost matter.
- Retrieval quality needs evaluation tests with real question sets.
- Script-style tests exist, but CI/pytest coverage can be stronger.
- Current rate limiter is in-memory, so multi-instance deployments should use Redis.

Next improvements:

1. Add retrieval evaluation tests.
   - Build a small set of expected Q&A pairs.
   - Check source accuracy and refusal behavior automatically.

2. Move uploads to object storage.
   - Local disk is fine for demo.
   - Production should use S3, Azure Blob, or another durable file store.

3. Add background processing for large files.
   - Upload returns quickly.
   - Worker chunks and embeds asynchronously.
   - UI shows processing status.

4. Add broader file support.
   - PDF and DOCX ingestion.
   - Extract text safely before chunking.

5. Improve observability.
   - Track retrieval scores, answer latency, provider errors, and token usage.

### Slide 12: Close

Claim: "The project proves a complete AI product loop, not just an API call."

Closing line:

> This server starts with protected documents, turns them into searchable chunks, retrieves the best evidence for each question, and returns an English answer with sources and user-scoped chat history.

## Exact 15-Minute Talk Track

### 0:00-2:00 Product Intro

"I built KB Chat Bot Dev AI, a developer knowledge-base chatbot. The idea is simple: instead of asking engineers to manually search through standards documents, they can ask a natural language question and get an English answer with cited sources. It is designed for internal engineering docs like API standards, database rules, logging standards, pull request guidelines, coding conventions, and Git flow."

"The important part is that the chatbot is not supposed to hallucinate. It must answer from the uploaded documents, cite sources, and say the information is not available when the docs do not cover the question."

### 2:00-4:00 Architecture

"The system has a React/Vite frontend and a FastAPI backend. The backend uses PostgreSQL with SQLAlchemy and Alembic. Authentication uses JWT access tokens and refresh tokens. Documents are uploaded as markdown, then the server chunks the text and generates embeddings. For chat, the user question is embedded, the server retrieves relevant chunks with pgvector and keyword fallback, and Gemini writes the final answer from that context."

"The original Week 6 spec mentions long-context, but my current implementation uses embedding-based RAG. I chose that because it scales better when documents grow. Instead of sending every document to the model, the server retrieves the most relevant chunks first."

### 4:00-6:00 Upload Demo

"Now I will upload a document. The route validates the file, saves it locally, creates the document row, splits the content into chunks, generates embeddings, stores them in the database, and records a version snapshot. After this, I can immediately ask a question about the new document."

### 6:00-10:00 Chat Demo

"Now I will ask questions from different categories. I want to show three things: the answer is in English, the answer matches the docs, and the source document is shown."

Use the recommended demo questions above.

### 10:00-11:00 Edge Case

"Now I will ask something outside the uploaded docs. The expected behavior is not to make up an answer. The chatbot should respond exactly that the information is not available in the current documents."

### 11:00-13:00 Security And Database

"The server also handles user isolation. Chat sessions are connected to the current user, so users only see their own history. Document permissions control which documents normal users can read, write, or own. Assistant messages are linked to source chunks through `message_sources`, which is how the app remembers where an answer came from."

### 13:00-15:00 Reflection

"The hardest part was making retrieval reliable. It is easy to get an answer from an LLM, but harder to make sure the answer is grounded in the right document and cites the right source. I improved this by chunking documents, storing embeddings, using pgvector search, and adding generic retrieval ranking so standards and policy docs are preferred over random examples."

"With one more week, I would add retrieval evaluation tests, move uploads to object storage, add background embedding jobs, and support PDFs/DOCX."

## Week 6 Rubric Mapping

### 40% Product Works

Show:

- Login works.
- Chat answers in English.
- Sources are cited.
- New upload can be queried.
- Out-of-docs question refuses to hallucinate.
- Session history works.
- No crash during demo.

### 30% Architecture Understanding

Say:

- React frontend sends requests to FastAPI.
- FastAPI routes call services.
- Services call repositories.
- Repositories query PostgreSQL.
- Upload creates chunks and embeddings.
- Chat retrieves chunks before calling Gemini.
- This implementation uses embeddings/pgvector, not long-context.

### 20% Critical Thinking

Say:

- Current limitations are markdown-only uploads, local file storage, external Gemini dependency, and limited retrieval evaluation.
- Improvements are object storage, background jobs, PDF/DOCX support, Redis rate limiting, CI tests, and retrieval quality metrics.

### 10% Code Quality

Say:

- Clear route/service/repository structure.
- Alembic migrations.
- `.env` config.
- Script tests.
- README setup docs.
- No API keys committed.

## Demo Checklist

Before presenting:

- Start PostgreSQL.
- Run backend migrations if needed.
- Start backend on `127.0.0.1:8000`.
- Start frontend on `127.0.0.1:5173`.
- Confirm admin login works.
- Confirm normal user login works.
- Confirm at least one API Standard, Logging, Pull Request, Database, Coding Convention, and Git Flow document is available.
- Confirm embeddings are enabled.
- Ask the demo questions once before the presentation.
- Keep Swagger open as backup: `http://127.0.0.1:8000/docs`.
- Keep README open as backup.
- Have a small markdown file ready for upload.
- Have a backup browser tab already logged in.

## Backup Demo Document

Use this content if you need a fresh upload during the demo:

```markdown
# Demo Release Policy

Production releases must include a rollback plan, test evidence, and an owner.

Use a staged rollout when the change affects authentication, payments, or data migration.

If a release fails health checks, stop the rollout and execute the rollback plan.
```

Question to ask after upload:

```text
What must a production release include?
```

Expected answer:

- rollback plan
- test evidence
- owner
- source should be the uploaded demo release policy

## Q&A Prep

### Why did you use embeddings instead of long-context?

Because long-context is simpler at small scale, but it gets expensive and noisy as the document set grows. Embeddings let the server retrieve only the most relevant chunks before asking Gemini to answer.

### What happens when a new document is uploaded?

The server validates the file, saves it, creates a document row, chunks the content, generates embeddings, stores chunks and vectors, and creates a version snapshot.

### Why do you need refresh tokens?

Access tokens are short-lived for safer API calls. Refresh tokens let the user stay logged in without retyping credentials, and because refresh tokens are stored/revoked in the database, logout and session revocation are possible.

### How do you prevent users from seeing each other's data?

Chat sessions are scoped to `current_user.id`, and document retrieval checks ownership plus document permissions before returning chunks to normal users.

### How do citations work?

The server tracks retrieved chunks as sources. When Gemini returns the answer, the assistant message is saved and linked to source document chunks through `message_sources`.

### What is the biggest risk?

Retrieval quality. If the wrong chunk is retrieved, the model may answer from the wrong evidence. The next improvement is a retrieval evaluation set that checks expected answer and expected source.
