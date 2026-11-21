; PoE 2 Toolkit installer (Inno Setup 7). Built by build_release.py --setup, which passes:
;   /DAppVersion=x.y.z  /DStage=<folder with python\ and toolkit\>  /O<output folder>
; Installs per user (no admin), into %LOCALAPPDATA%\Programs\PoE 2 Toolkit. Data lives in %LOCALAPPDATA%\PoE2Toolkit.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Stage
  #define Stage "F:\Tools\poe2kit-build\stage"
#endif

[Setup]
AppId={{6B0F2D2E-7B1C-4E1A-9F2B-2E5C0A9D4F21}
AppName=PoE 2 Toolkit
AppVersion={#AppVersion}
AppVerName=PoE 2 Toolkit {#AppVersion}
AppPublisher=PoE 2 Toolkit
DefaultDirName={localappdata}\Programs\PoE 2 Toolkit
DefaultGroupName=PoE 2 Toolkit
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=PoE2Toolkit-Setup-{#AppVersion}
SetupIconFile={#Stage}\toolkit\dashboard\poe2kit.ico
UninstallDisplayIcon={app}\toolkit\dashboard\poe2kit.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Stage}\LICENSES.md
InfoBeforeFile={#Stage}\README.md

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start PoE 2 Toolkit with Windows (keeps prices and alerts up to date)"; GroupDescription: "Background:"; Flags: unchecked

[Files]
Source: "{#Stage}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Stage}\toolkit\*"; DestDir: "{app}\toolkit"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Stage}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\CLAUDE-GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PoE 2 Toolkit"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\toolkit\tray.pyw"""; WorkingDir: "{app}\toolkit"; IconFilename: "{app}\toolkit\dashboard\poe2kit.ico"
Name: "{group}\Using PoE 2 Toolkit with Claude"; Filename: "https://github.com/xoxoFaith1993/poe2-toolkit/blob/main/CLAUDE-GUIDE.md"
Name: "{group}\Uninstall PoE 2 Toolkit"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PoE 2 Toolkit"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\toolkit\tray.pyw"""; WorkingDir: "{app}\toolkit"; IconFilename: "{app}\toolkit\dashboard\poe2kit.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PoE2Toolkit"; ValueData: """{app}\python\pythonw.exe"" ""{app}\toolkit\tray.pyw"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\toolkit\tray.pyw"""; WorkingDir: "{app}\toolkit"; Description: "Start PoE 2 Toolkit now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-CimInstance Win32_Process -Filter \""Name like 'python%'\"" | Where-Object {{ $_.CommandLine -like '*{app}*' } | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }"""; Flags: runhidden; RunOnceId: "StopToolkit"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\toolkit\__pycache__"
Type: filesandordirs; Name: "{app}\toolkit\poe2kit\__pycache__"
Type: filesandordirs; Name: "{app}\toolkit\patch-watch"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var ResultCode: Integer;
begin
  { an update: stop the running tray + monitor from this install folder first }
  Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name like ''python%''\" | Where-Object { $_.CommandLine -like ''*' + ExpandConstant('{app}') + '*'' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Data: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Data := ExpandConstant('{localappdata}\PoE2Toolkit');
    if DirExists(Data) then
      if MsgBox('Also delete your PoE 2 Toolkit data (prices, builds, settings, downloaded Path of Building)?' + #13#10 +
                Data, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Data, True, True, True);
  end;
end;
