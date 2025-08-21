# RS-RraphRAG
## Démarrage

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

```bash
# depuis la racine du projet v2
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

pip install -U pip
pip install -r requirements.txt

# Démarrage API
uvicorn app.main:app --reload --host %HOST% --port %PORT%
# (ou remplace %HOST%/%PORT% si ta console ne développe pas les variables .env)
