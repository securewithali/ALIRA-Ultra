@echo off
rem ============================================================
rem  ALIRA — one-click install
rem  1) pip se ALIRA install/upgrade
rem  2) Windows startup ON  (PC start/restart par ALIRA orb ke saath khud chalu)
rem  3) ALIRA abhi background mein chalu (screen par mini orb)
rem ============================================================
title ALIRA install
echo.
echo  [1/2] ALIRA install ho rahi hai...
python -m pip install --upgrade ALIRA-ai-assistant
if errorlevel 1 (
    echo.
    echo  [X] pip install fail hua. Internet / Python (3.10+) check karo.
    pause
    exit /b 1
)
echo.
echo  [2/2] Startup set ho raha hai aur ALIRA chalu ho rahi hai...
python -m ALIRA install
echo.
echo  Done! ALIRA ka orb screen par aa jayega. Orb par click karke controls dekho,
echo  double-click karke ALIRA kholo. Band karna ho to:  python -m ALIRA uninstall
echo.
pause
