# Enterprise Multi-Agent RAG Platform

## Overview
This is a production-grade backend for a Multi-Agent RAG Platform built using Python, FastAPI, LangChain, and LangGraph. It is designed around modular, scalable, clear architecture principles supporting features like Chat, RAG, File Analysis, and dynamic report generation.

## Features Supported
- **Multi-Agent System via LangGraph:** A router agent delegating tasks among Search, RAG, Summary, Data Analysis, and Reporting. 
- **Document Processing:** Support for PDF, DOCX, CSV.
- **Robust Database Engine:** Built with SQLAlchemy pointing to SQLite (default dev setup) but scalable up to PostgreSQL environments.
- **REST APIs:** Full-featured FastAPI routing for User Management, Doc Uploads, AI Graph Invocation (`/chat/query`), and file generation.

## Quick Start Development
1. Start up a virtual environment.
```bash
python -m venv venv
.\venv\Scripts\activate
```
2. Install Requirements.
```bash
pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and fill in necessary keys.
4. Run the Dev Server.
```bash
uvicorn app.main:app --reload
```
API Documentation available at: `http://localhost:8000/api/v1/openapi.json` and `http://localhost:8000/docs`.

## Architecture Details
```
app/
├── agents/            # LangGraph multi-agent workflow
├── core/              # Security and settings (JWT/OAuth)
├── database/          # Database definitions
├── models/            # SQLAlchemy Database relations
├── routers/           # FastAPI entry points
├── schemas/           # Request / Response Pydantic models
├── services/          # Business logic processing
└── utils/             # Core functionalities (S3, logger)
```
