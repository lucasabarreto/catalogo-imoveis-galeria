@echo off
cd /d "C:\Users\Lucas Barreto\Downloads\catalogo-imoveis-galeria"
"C:\Users\Lucas Barreto\AppData\Local\Programs\Python\Python314\python.exe" scraper.py >> logs\scheduled_run.log 2>&1
