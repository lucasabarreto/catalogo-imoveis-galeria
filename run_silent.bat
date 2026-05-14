@echo off
cd /d "C:\Users\Lucas Barreto\Downloads\catalogo-imoveis-galeria"
"C:\Users\Lucas Barreto\AppData\Local\Programs\Python\Python314\python.exe" scraper.py >> logs\scheduled_run.log 2>&1

:: Push feeds atualizados para o GitHub (atualiza o XML publico)
git add output/output.csv output/output.xml output/google_ads_real_estate_feed.csv >> logs\scheduled_run.log 2>&1
git commit -m "Atualiza feeds %date% %time:~0,5%" >> logs\scheduled_run.log 2>&1
git push >> logs\scheduled_run.log 2>&1
