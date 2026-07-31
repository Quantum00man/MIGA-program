Option Explicit

Dim shell, fso, projectDir, pythonwPath, launcherPath, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = projectDir & "\.venv\Scripts\pythonw.exe"
launcherPath = projectDir & "\launcher.pyw"

If Not fso.FileExists(pythonwPath) Then
    MsgBox "Python environment not found: " & pythonwPath, vbCritical, "MIGA Hardware Controller"
    WScript.Quit 1
End If

command = """" & pythonwPath & """ """ & launcherPath & """"
shell.Run command, 0, False

