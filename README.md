# HYDRA – Intelligent Railway Maintenance Block Planner

> **Prototype** for Smart India Hackathon – Railway Maintenance Block Planning
>
> Decision Support Prototype – Human Approval Required

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend, later)

### Installation

```bash
cd hydra
pip install -r requirements.txt
```

### 1. Generate Demo Data

```bash
python backend/generate_data.py
```

### 2. Run Full Pipeline (CLI)

```bash
python backend/run_pipeline.py
```

This runs the complete pipeline:
- Loads synthetic TMS/SMMS/TDMS/COA data
- Normalizes into unified task pool
- Calculates priority scores
- Finds maintenance block windows
- Discovers multi-department bundling groups
- Runs baseline (decentralized) scheduler
- Runs OR-Tools CP-SAT optimizer
- Validates the schedule
- Prints comparison

### 3. Run Backend API

```bash
uvicorn backend.main:app --reload
```

### 4. Run Frontend (after setup)

```bash
cd frontend
npm install
npm run dev
```

### 5. Run Tests

```bash
pytest
```

## Architecture

```
TMS + SMMS + TDMS + COA
        ↓
Data Normalization
        ↓
Priority Scoring (rule-based)
        ↓
Multi-Department Coordination
        ↓
Available Block Windows
        ↓
OR-Tools CP-SAT Optimization
        ↓
Optimized Weekly Block Plan
```

## Tech Stack

| Layer    | Technology                  |
|----------|-----------------------------|
| Backend  | Python, FastAPI, Pandas     |
| Solver   | Google OR-Tools (CP-SAT)    |
| Database | SQLite                      |
| Frontend | React, TypeScript, Tailwind |
| Testing  | pytest                      |

## Key Features

- **Multi-department bundling**: Engineering + Signal + Traction tasks within 1 km bundled into joint blocks
- **Real optimization**: OR-Tools CP-SAT solver, not simulated results
- **Priority scoring**: Transparent, rule-based (no ML black box)
- **Train conflict avoidance**: Confirmed trains are hard constraints
- **Test mode**: Inject disruptions (train delay, new defect) and re-optimize
- **Baseline comparison**: HYDRA vs decentralized planning metrics

## Data

All data is **fictional/synthetic**. No real railway systems are connected.
