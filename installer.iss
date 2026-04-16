#define MyAppName "Phoenix Valve Checkout Tool"
#define MyAppPublisher "ATS Inc."
#define MyAppExeName "PhoenixCheckoutTool.exe"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/JustinGlave/Phoenix-Checkout-Tool
AppSupportURL=https://github.com/JustinGlave/Phoenix-Checkout-Tool/issues
AppUpdatesURL=https://github.com/JustinGlave/Phoenix-Checkout-Tool/releases

; Install to LocalAppData so no admin rights are needed and the auto-updater works
DefaultDirName={localappdata}\ATS Inc\Phoenix Valve Checkout Tool
DefaultGroupName=ATS Inc\Phoenix Valve Checkout Tool
DisableProgramGroupPage=yes

; Output
OutputDir=dist
OutputBaseFilename=PhoenixCheckoutToolSetup
SetupIconFile=PTT_Normal_green.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; No admin required (LocalAppData is user-writable)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

; Compression
Compression=lzma2/ultra64
SolidCompression=yes

; Wizard appearance
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Include the entire PyInstaller output folder
Source: "dist\PhoenixCheckoutTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Desktop shortcut — {userdesktop} avoids access denied on no-admin installs
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Offer to launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up any files the app creates in its install folder
Type: filesandordirs; Name: "{app}"

[Code]
// Ask user if they want to keep their data on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  MsgResult: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\ATS Inc\Phoenix Valve Checkout Tool');
    if DirExists(DataDir) then
    begin
      MsgResult := MsgBox(
        'Do you want to delete your application data?' + #13#10#13#10 +
        'Click Yes to delete all data, or No to keep it.',
        mbConfirmation, MB_YESNO
      );
      if MsgResult = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
