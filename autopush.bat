@echo off
title GITHUB AUTO-PUSHER
color 0A

:loop
cls
echo ==============================================
echo    AVTOMATICHESKOE SOHRANENIE NA GITHUB
echo ==============================================
echo.
echo [ %time% ] Dobavlenie failov...
git add .

echo [ %time% ] Fiksaciya izmeneniy...
git commit -m "Auto-save: %date% %time%"

echo [ %time% ] Otpravka na server...
git push origin main

echo.
echo ==============================================
echo    USPESHNO! Sleduyushchiy raz cherez 10 min.
echo ==============================================
:: 10000 секунд = 10 минут
timeout /t 1000 >nul

goto loop