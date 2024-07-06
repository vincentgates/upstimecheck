@echo off
python -m venv env
call env\Scripts\activate
python -m pip install --upgrade pip
pip install -r config/development/requirements.txt
echo Environment setup complete. You can now run the server with `python run.py`.
