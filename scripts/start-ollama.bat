@echo off
set OLLAMA_MODELS=D:\ollama-models\models
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
