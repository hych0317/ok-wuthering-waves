@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ============================================================
REM  okww 每日一条龙 - 启动脚本
REM  功能：检测当天是否已运行 → 检测网络 → 弹窗确认 → 执行任务
REM  用法：
REM    okww_start-daily.bat          正常启动（含每日检测）
REM    okww_start-daily.bat /f       跳过检测，强制执行
REM    okww_start-daily.bat /check   只检查启动环境，不启动程序
REM  开机自启：将本脚本的快捷方式放入
REM    shell:startup  (Win+R 输入即可打开启动文件夹)
REM ============================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "MARKER_FILE=%SCRIPT_DIR%.okww_last_run"
set "PROMPT_SCRIPT=%SCRIPT_DIR%okww_prompt.ps1"
set "LAUNCHER_LOG=%SCRIPT_DIR%logs\okww-start-daily.log"

if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs" >nul 2>&1
>>"%LAUNCHER_LOG%" echo [%date% %time%] launcher started args=%*

REM === 1. 获取游戏日期（北京时间 04:00 为每日分界）===
REM    北京时间 = UTC+8；04:00 前仍算前一天
for /f %%i in ('powershell -NoProfile -Command "$bj = (Get-Date).ToUniversalTime().AddHours(8); if ($bj.Hour -lt 4) { $bj.AddDays(-1).ToString('yyyy-MM-dd') } else { $bj.ToString('yyyy-MM-dd') }"') do set "TODAY=%%i"
if not defined TODAY (
    echo [失败] 无法计算游戏日期。
    >>"%LAUNCHER_LOG%" echo [%date% %time%] failed to calculate game date
    pause
    exit /b 1
)

REM --- 强制模式：保留运行日期，但跳过其余检测直接运行 ---
if /i "%~1"=="/check" goto :run_task
if /i "%~1"=="/f" goto :run_task

echo.
echo [%TODAY%] okww 每日一条龙 - 启动检测（每日分界：北京时间 04:00）
echo.

REM === 2. 检查今天是否已运行 ===
set "LAST_RUN="
if exist "%MARKER_FILE%" set /p LAST_RUN=<"%MARKER_FILE%"
if "%LAST_RUN%"=="%TODAY%" (
    echo [跳过] 今天已经运行过，无需重复执行。
    >>"%LAUNCHER_LOG%" echo [%date% %time%] skipped already completed date=%TODAY%
    timeout /t 5
    exit /b 0
)

REM === 3. 检查网络连接（最多重试 5 次，间隔 30 秒）===
set "RETRY=0"
:net_check
set /a RETRY+=1
if %RETRY% gtr 5 (
    echo [失败] 网络不可用（已重试 5 次），退出。
    >>"%LAUNCHER_LOG%" echo [%date% %time%] network unavailable after retries
    timeout /t 5
    exit /b 1
)
echo [网络] 第 %RETRY%/5 次检测...
ping -n 1 -w 3000 223.5.5.5 >nul 2>&1
if errorlevel 1 (
    echo [网络] 未连接，30 秒后重试...
    timeout /t 30 /nobreak >nul
    goto :net_check
)
echo [网络] 已连接

REM === 4. 弹出确认对话框（超时自动运行）===
echo [确认] 等待用户响应...
if exist "%PROMPT_SCRIPT%" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%PROMPT_SCRIPT%"
    set "PROMPT_EXIT=%ERRORLEVEL%"
    if "!PROMPT_EXIT!"=="2" (
        echo [取消] 用户选择不运行，退出。
        >>"%LAUNCHER_LOG%" echo [%date% %time%] cancelled by user
        timeout /t 3
        exit /b 0
    )
) else (
    echo [警告] 未找到 okww_prompt.ps1，跳过确认并继续运行。
    >>"%LAUNCHER_LOG%" echo [%date% %time%] prompt script missing, continuing
)
echo [确认] 用户确认运行

:run_task
REM === 5. 执行任务；任务成功后由多账号任务写入运行标记 ===
echo.
echo ========================================
echo   开始执行 okww 每日一条龙/多账号自动切换
echo ========================================
echo.
echo 正在激活 conda 环境 okww...
call conda activate okww
if errorlevel 1 (
    echo [失败] 无法激活 conda 环境 okww。
    >>"%LAUNCHER_LOG%" echo [%date% %time%] conda activate failed
    pause
    exit /b 1
)

set "OKWW_DAILY_RUN_MARKER=%MARKER_FILE%"
set "OKWW_DAILY_RUN_DATE=%TODAY%"
if /i "%~1"=="/check" (
    echo [检查通过] 日期、日志目录和 conda 环境均可用。
    >>"%LAUNCHER_LOG%" echo [%date% %time%] environment check passed
    exit /b 0
)
>>"%LAUNCHER_LOG%" echo [%date% %time%] starting python date=%TODAY%
python main.py -t 2
set "TASK_EXIT=%ERRORLEVEL%"
>>"%LAUNCHER_LOG%" echo [%date% %time%] python exited code=%TASK_EXIT%

if not "%TASK_EXIT%"=="0" (
    echo [失败] 程序启动或运行异常，退出码：%TASK_EXIT%
    echo 启动日志：%LAUNCHER_LOG%
    pause
)
exit /b %TASK_EXIT%
