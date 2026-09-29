' ==============================================================================
' AutoApplyJobs v3.3 - 9-to-5 Autonomous Silent Background Runner
' Spawns the background scheduler and API daemon completely hidden
' with 0 console windows and 0 taskbar clutter for workday execution.
' ==============================================================================

Option Explicit
Dim objShell, objFSO, strScriptDir, strBatFile

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strBatFile = strScriptDir & "\run_9to5_background.bat"

' WindowStyle 0 = Hidden window, bWaitOnReturn False = Asynchronous background
objShell.Run Chr(34) & strBatFile & Chr(34) & " --silent", 0, False

Set objShell = Nothing
Set objFSO = Nothing
