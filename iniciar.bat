@echo off
chcp 65001 >nul
title Jane Cabeleireira Hair - Servidor
cd /d "%~dp0"

echo ============================================
echo   Jane Cabeleireira Hair — Iniciando sistema
echo ============================================
echo.

REM ---- verifica se Python esta instalado ----
where python >nul 2>nul
if %errorlevel%==0 ( set "PY=python" & goto :achou )
where python3 >nul 2>nul
if %errorlevel%==0 ( set "PY=python3" & goto :achou )

echo [ERRO] Python nao foi encontrado no seu computador!
echo.
echo 1. Acesse https://www.python.org/downloads/
echo 2. Baixe e instale o Python (versao 3.10 ou superior)
echo 3. Durante a instalacao, MARQUE a opcao "Add Python to PATH"
echo 4. Depois de instalar, de dois cliques neste arquivo novamente.
echo.
pause
exit /b 1

:achou
echo Python encontrado: %PY%
echo.

REM ---- instala dependencias ----
echo Instalando dependencias (so precisa na primeira vez)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel instalar as dependencias.
    echo Verifique sua internet e tente novamente.
    pause
    exit /b 1
)
echo Dependencias OK.
echo.

REM ---- abre o navegador ----
echo Abrindo o sistema no navegador...
start "" http://localhost:5000
echo.

REM ---- roda o servidor ----
echo ============================================
echo  SISTEMA RODANDO! Nao feche esta janela.
echo  Acesse: http://localhost:5000
echo  Para parar: aperte Ctrl+C nesta janela
echo ============================================
echo.
%PY% server.py

echo.
echo O servidor parou. Pressione qualquer tecla para fechar.
pause >nul
