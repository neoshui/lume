; Lume Windows installer. The project version is supplied by /DMyAppVersion=...
#ifndef MyAppVersion
  #define MyAppVersion "1.1.1"
#endif

#define MyAppName "Lume"
#define MyAppPublisher "Lume"
#define MyAppExeName "Lume.exe"

[Setup]
AppId={{B5B5CB41-2D4F-49F0-9C1A-0CE25B24A6A8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Lume
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=Lume-windows-x86_64-Setup
SetupIconFile=..\lume.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Files]
Source: "..\dist\Lume.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Lume"; Filename: "{app}\{#MyAppExeName}"

[Tasks]
Name: "autostart"; Description: "登录 Windows 后自动启动 Lume（后台运行）"; GroupDescription: "启动选项:"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Lume"; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 Lume"; Flags: nowait postinstall skipifsilent
