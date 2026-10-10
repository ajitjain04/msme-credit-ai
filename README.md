# MSME Credit AI

An explainable AI-based alternative credit assessment platform for Indian MSMEs (Micro, Small and Medium Enterprises) with limited traditional credit history.

It estimates a business’s probability of default using alternative data—banking activity, GST compliance, and digital-payment signals—then converts that result into a transparent credit score, risk band, and SHAP-based explanation.

> The included dataset is synthetic and the project is for educational/prototype use. It must not be used for real lending decisions without production validation, governance, consent-based data access, monitoring, and regulatory review.

## Key capabilities

- Alternative-data credit scoring for thin-file MSMEs
- Credit score range of **300–900**
- Default-probability prediction and calibrated risk bands
- Explainable predictions using **SHAP**
- FastAPI backend with interactive Swagger documentation
- Next.js dashboard for:
  - Business evaluation
  - Score gauge and risk assessment
  - SHAP driver analysis
  - PDF credit-report download
  - Portfolio-level analytics
  - Fairness audit using Disparate Impact Ratio (DIR)
- PostgreSQL support, with SQLite fallback for local development
- Synthetic Indian MSME data generator
- Automated test suite with 30 tests

## Risk bands

| Risk band | Credit score | Default probability |
|---|---:|---:|
| Low Risk | 750+ | Below 20% |
| Medium Risk | 600–749 | 20%–50% |
| High Risk | Below 600 | Above 50% |

## Data used

The synthetic dataset represents 5,000 Indian MSMEs and includes:

- Business age, category, state, and employee count
- Average monthly inflow and outflow
- Account balance, payment-bounce count, account vintage, and cash-flow volatility
- GST registration, turnover, filing regularity, and filing delays
- UPI transaction ratio, POS usage, and digital-payment adoption
- A synthetic default label (`credit_default_status`)

See [the data dictionary](docs/data_dictionary.md) for detailed feature definitions and the data-generation methodology.

## Architecture

```text
Synthetic MSME Data
        │
        ▼
Feature Engineering + Preprocessing
        │
        ▼
Trained & Calibrated ML Model
        │
        ├── Default Probability
        ├── Credit Score (300–900)
        ├── Risk Band
        └── SHAP Explanations
        │
        ▼
FastAPI Backend + Database
        │
        ▼
Next.js Dashboard / PDF Reports / Portfolio Analytics
```

## Tech stack

**Machine learning**

- Python 3.11
- pandas and NumPy
- scikit-learn
- XGBoost and LightGBM
- Optuna
- SHAP
- joblib

**Backend**

- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- SQLite fallback
- Uvicorn

**Frontend**

- Next.js 15
- React 19
- TypeScript
- Tailwind CSS
- Plotly
- Axios

**Testing and reporting**

- pytest
- ReportLab
- Jupyter notebooks

## Project structure

```text
msme-credit-ai/
├── backend/              # FastAPI API, schemas, database models, CRUD layer
├── data/
│   ├── generate_data.py  # Synthetic MSME data generator
│   ├── synthetic/        # Source synthetic dataset
│   └── processed/        # Train/test data and local SQLite fallback
├── dashboard/            # Legacy Streamlit dashboard
├── docs/                 # Data dictionary, progress log, visuals
├── frontend/             # Next.js dashboard
├── model/                # Training, calibration, scoring, SHAP, fairness logic
│   └── artifacts/        # Saved model, calibration and metrics artifacts
├── notebooks/            # Exploratory data analysis
├── scripts/              # Database initialization scripts
└── tests/                # Model and API test suite
```

## Getting started

### 1. Clone the repository

```powershell
git clone https://github.com/ajitjain04/msme-credit-ai.git
cd msme-credit-ai
```

### 2. Create and activate a Python environment

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure the database

The backend uses SQLite automatically when `DATABASE_URL` is not set.

To use PostgreSQL, copy `.env.example` to `.env` and set your own connection string:

```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD_HERE@localhost:5432/msme_credit
```

### 4. Start the backend

```powershell
python -m uvicorn backend.main:app --reload
```

Open:

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

### 5. Start the Next.js dashboard

In a second terminal:

```powershell
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then run:

```powershell
npm run dev
```

Open http://localhost:3000.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | API health check |
| `POST` | `/api/v1/evaluate` | Score an MSME and save its assessment |
| `GET` | `/api/v1/company/{company_id}` | Retrieve company profile and assessment history |
| `GET` | `/api/v1/company/{company_id}/report/pdf` | Download a PDF credit report |
| `GET` | `/api/v1/analytics/portfolio` | Retrieve portfolio risk analytics |
| `GET` | `/api/v1/analytics/fairness` | Run a fairness audit using DIR |

## Model outputs

For every evaluated MSME, the platform returns:

- Default probability
- Credit score from 300 to 900
- Risk band: Low, Medium, or High
- Top risk-increasing factors
- Top risk-reducing factors
- SHAP values for model explainability
- Downloadable one-page PDF credit report

## Model performance

The saved calibrated Logistic Regression model achieved approximately:

| Metric | Result |
|---|---:|
| Test ROC-AUC | 0.744 |
| Test PR-AUC | 0.350 |
| Default recall | 0.669 |
| Default precision | 0.298 |
| Default F1-score | 0.413 |

These figures are measured on the repository’s synthetic test data and should not be interpreted as real-world lending performance.

## Fairness auditing

The project includes a Disparate Impact Ratio (DIR) audit across business categories and states.

A DIR below `0.80` is flagged for investigation using the commonly referenced four-fifths rule. A low DIR is not proof of unfairness by itself; it should be reviewed alongside cohort size and observed default rates.

## Testing

Run the automated suite with:

```powershell
pytest tests/ -v
```

The repository currently contains 30 model, calibration, predictor, and API tests.

## Important limitations

- All data is synthetic.
- Model performance does not demonstrate real lending readiness.
- Real deployment requires consent-based data access, robust validation, security controls, bias monitoring, model governance, and compliance with applicable financial regulations.
- State and business category are audited because risk-relevant variables can still create disparate outcomes.

## Future work

- Docker and deployment configuration
- Production authentication and authorization
- Model monitoring and drift detection
- Real consent-based Account Aggregator data integration
- Stronger fairness and governance controls
- CI/CD pipeline and cloud deployment

## License

Add a license before using or distributing this project publicly.