start cmd.exe /k "npm run start"
call .venv\Scripts\activate
echo Running `python run.py`
python run.py

@REM git archive --format=zip -o output.zip HEAD