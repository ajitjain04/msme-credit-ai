"""Creates the full folder and file structure for the MSME credit project."""
from pathlib import Path

folders = [
    "data/raw",            # downloaded real datasets (not uploaded to GitHub)
    "data/synthetic",      # our generated MSME dataset
    "data/processed",      # cleaned data and train/test splits
    "notebooks",           # Jupyter notebooks for EDA and experiments
    "model/artifacts",     # saved trained model, preprocessor, SHAP explainer
    "backend",             # FastAPI application
    "dashboard/components",# Streamlit app pieces (charts, gauge)
    "tests",               # pytest test files
    "docs/images",         # diagrams and charts for README and report
]

files = [
    "data/generate_data.py",
    "model/__init__.py", "model/config.py", "model/preprocessing.py",
    "model/train.py", "model/tune.py", "model/evaluate.py",
    "model/scoring.py", "model/explainer.py", "model/predictor.py",
    "backend/__init__.py", "backend/main.py", "backend/schemas.py",
    "backend/database.py", "backend/db_models.py", "backend/crud.py",
    "dashboard/app.py", "dashboard/components/__init__.py",
    "dashboard/components/charts.py",
    "tests/__init__.py", "tests/test_scoring.py",
    "tests/test_predictor.py", "tests/test_api.py",
    "docs/data_dictionary.md",
    "README.md", "CLAUDE.md", "requirements.txt", ".gitignore",
]

for folder in folders:
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / ".gitkeep").touch()   # lets Git track empty folders

for file in files:
    Path(file).touch(exist_ok=True)

print("Project structure created!")