; Copyright (c) 2026 jerry wolff

#define AppName "FinOps CCoE Live Reporting"
#define AppVersion "1.2.5"
#define AppPublisher "FinOps CCoE"
#define AppExeName "FinOpsCCoE.exe"

[Setup]
AppId={{E14404C2-89DC-4EF2-9806-827F4915C68E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\FinOpsCCoE
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=FinOpsCCoE-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

[Code]
var
  AuthRuntimeChecked: Boolean;
  AuthRuntimeNeeded: Boolean;
  AuthRuntimeDirectory: String;

function NeedsAuthenticationRuntime: Boolean;
var
  RuntimeDirectory, PythonPath, Parameters: String;
  ResultCode: Integer;
begin
  RuntimeDirectory := ExpandConstant('{app}\azure-cli');
  if (not AuthRuntimeChecked) or (AuthRuntimeDirectory <> RuntimeDirectory) then
  begin
    AuthRuntimeChecked := True;
    AuthRuntimeDirectory := RuntimeDirectory;
    AuthRuntimeNeeded := True;
    PythonPath := RuntimeDirectory + '\python.exe';
    if FileExists(PythonPath) and FileExists(RuntimeDirectory + '\bin\az.cmd') then
    begin
      ExtractTemporaryFile('finops-runtime-check.py');
      ExtractTemporaryFile('windows-runtime.json');
      Parameters := '-IB "' + ExpandConstant('{tmp}\finops-runtime-check.py') +
        '" "' + ExpandConstant('{tmp}\windows-runtime.json') + '"';
      if Exec(PythonPath, Parameters, RuntimeDirectory, SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        AuthRuntimeNeeded := ResultCode <> 0;
    end;
    if AuthRuntimeNeeded then
      Log('AuthRuntime: missing, damaged, or incompatible; installing the bundled component.')
    else
      Log('AuthRuntime: healthy compatible runtime found; preserving existing prerequisite files.');
  end;
  Result := AuthRuntimeNeeded;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
	ResultCode: Integer;
begin
	{ A running PyInstaller process locks python311.dll and other bundled files. }
	Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExeName}', '',
		SW_HIDE, ewWaitUntilTerminated, ResultCode);
	Result := '';
end;

[Files]
Source: "..\app\desktop_runtime.py"; DestDir: "{tmp}"; DestName: "finops-runtime-check.py"; Flags: dontcopy
Source: "..\windows-runtime.json"; DestDir: "{tmp}"; Flags: dontcopy
Source: "..\dist\FinOpsCCoE\*"; DestDir: "{app}"; Excludes: "azure-cli\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\FinOpsCCoE\azure-cli\*"; DestDir: "{app}\azure-cli"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: NeedsAuthenticationRuntime

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent