@echo off
cd /d %~dp0
title RSM 实验助手 - 选择示例
echo.
echo  ============================================
echo        选择要载入的示例实验（公开文献数据）
echo  ============================================
echo   1. 提取产率     Sci Rep 2022, 3因素  [推荐]模型质量好
echo   2. 总多酚含量   Sci Rep 2022, 3因素        弱模型演示
echo   3. PLGA包封率   Biomed Res Int 2014, 4因素
echo   4. PLGA粒径     Biomed Res Int 2014, 4因素  最小化目标
echo.
set /p choice=请输入编号(1-4)后回车，直接回车=1: 
if "%choice%"=="" set choice=1
if "%choice%"=="1" set key=yield
if "%choice%"=="2" set key=tpc
if "%choice%"=="3" set key=ee
if "%choice%"=="4" set key=size
python demo_launch.py %key%
if errorlevel 1 pause
