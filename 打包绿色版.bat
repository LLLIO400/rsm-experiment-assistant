@echo off
chcp 936 >nul
title 打包 RSM 实验助手 绿色版
cd /d %~dp0
echo.
echo  [1/4] 检查 PyInstaller ...
python -m PyInstaller --version >nul 2>&1 || pip install pyinstaller
echo.
echo  [2/4] 开始打包（要几分钟，请勿关闭窗口）...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "RSM实验助手" main.py
if errorlevel 1 (
    echo  打包失败！请把上面的红色错误发给开发者。
    pause
    exit /b 1
)
echo.
echo  [3/4] 复制随行文件（技能/示例启动）...
xcopy /y /i skills "dist\RSM实验助手\skills\" >nul

REM 安全清理：不携带本机隐私（AI 配置 / 实验数据 / 输出图），软件首次运行自动重建
if exist "dist\RSM实验助手\config.json" del /q "dist\RSM实验助手\config.json"
if exist "dist\RSM实验助手\data" rmdir /s /q "dist\RSM实验助手\data"
if exist "dist\RSM实验助手\output" rmdir /s /q "dist\RSM实验助手\output"
mkdir "dist\RSM实验助手\data" 2>nul
mkdir "dist\RSM实验助手\output" 2>nul
(
    echo @echo off
    echo "RSM实验助手.exe" --demo yield
) > "dist\RSM实验助手\打开示例实验.bat"
echo.
echo  [4/4] 部署到桌面 ...
set "DEST=%USERPROFILE%\Desktop\RSM实验助手-绿色版"
if exist "%DEST%" rmdir /s /q "%DEST%"
xcopy /y /e /i "dist\RSM实验助手" "%DEST%" >nul
echo.
echo  完成！绿色版已放在桌面：RSM实验助手-绿色版
echo  双击里面的 RSM实验助手.exe 即可运行（无需安装 Python）。
explorer "%DEST%"
pause
