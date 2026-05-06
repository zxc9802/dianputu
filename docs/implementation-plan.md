# MVP Implementation Plan

## Task 1: Backend Model Configuration

Create backend modules that read model settings from environment variables and expose sanitized model metadata to the frontend.

Files:

- `backend/app/core/config.py`
- `backend/app/services/text_model.py`
- `backend/app/services/image_model.py`
- `backend/tests/test_model_payloads.py`

Verification:

- `python -m unittest discover backend/tests -v`

## Task 2: Backend API

Create FastAPI routes for health checks, model metadata, extraction, module selection, generation jobs, and export metadata.

Files:

- `backend/app/main.py`
- `backend/app/schemas.py`
- `backend/app/routers/models.py`
- `backend/app/routers/projects.py`
- `backend/requirements.txt`

## Task 3: Frontend Wizard

Create a Next.js app matching the approved five-step UI:

- Upload materials
- Select category and style
- Confirm extracted fields
- Select modules
- Preview and export

Files:

- `frontend/app/page.tsx`
- `frontend/app/layout.tsx`
- `frontend/app/globals.css`
- `frontend/components/*.tsx`
- `frontend/lib/*.ts`

## Task 4: Integration

Wire frontend actions to backend endpoints through `frontend/lib/api.ts`. Keep demo fallback data so the UI remains usable when backend keys are not configured.

## Task 5: Local Run

After user confirms dependency installation:

- `npm.cmd install --prefix frontend`
- `py -m pip install -r backend/requirements.txt`
- `npm.cmd --prefix frontend run dev`
- `py -m uvicorn backend.app.main:app --reload --port 8000`
