@echo off
chcp 936 >nul
title 启动 LM Studio 本地服务
echo.
echo  正在启动 LM Studio 本地服务（AI 面板用）...
%USERPROFILE%\.lmstudio\bin\lms.exe server start
echo.
echo  完成。此窗口可以关闭；LM Studio 程序请保持运行。
pause
