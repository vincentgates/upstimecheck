@echo off
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r config/requirements.txt
echo Environment setup complete. You can now run the server with `python run.py`.
