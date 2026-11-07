# Windows build machine setup

One-off setup to build the original application and the harness. Commands
run in **PowerShell**. Steps marked *(admin)* need "Run as administrator".

SSH comes first: once it works, every later step can run from the Mac
(`ssh win-build ...`), and only launching the GUI needs someone at the
machine.

## 1. OpenSSH server *(admin)*

Install the standalone Win32-OpenSSH package. The built-in
`Add-WindowsCapability` route depends on Windows servicing and can fail with a
`COMException`.

```powershell
winget install --id Microsoft.OpenSSH.Preview -e --source winget
Start-Service sshd
Set-Service sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH Server" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
```

Keep PowerShell as the default shell: the toolchain is Windows-native, and
WSL is still reachable with `wsl` after connecting.

### Authorise the Mac's key

For an **administrator** account, Windows OpenSSH reads keys only from
`C:\ProgramData\ssh\administrators_authorized_keys`, not `~\.ssh`. Download
the keys published on GitHub instead of typing or pasting one:

```powershell
curl.exe -s https://github.com/<github-user>.keys -o C:\ProgramData\ssh\administrators_authorized_keys
ssh-keygen -lf C:\ProgramData\ssh\administrators_authorized_keys
icacls.exe C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

- Type `curl.exe`, not `curl`: in Windows PowerShell `curl` is an alias for `Invoke-WebRequest`, which writes a file sshd can't parse
- `ssh-keygen -lf` must list the keys. "Not a public key file" means the file is corrupt
- `icacls` must leave exactly `BUILTIN\Administrators:(F)` and `NT AUTHORITY\SYSTEM:(F)`. sshd ignores the file otherwise

### Mac SSH config

On a dual-boot machine the Windows and Linux boots share an IP but have different host keys.
`HostKeyAlias` keeps their `known_hosts` entries apart:

```
Host win-build
  Hostname <windows-machine-ip>
  User <windows-user>
  HostKeyAlias win-build
  IdentityFile <path-to-private-key>
  IdentitiesOnly yes
  UseKeychain yes
  ServerAliveInterval 60
```

Test: `ssh win-build whoami` prints `<machine-name>\<windows-user>`.

## 2. Toolchain

These run fine over SSH. `--quiet` is needed for Visual Studio because an SSH
session has no desktop to show the installer window on.

```powershell
winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --silent
winget install --id Microsoft.VisualStudio.2022.Community -e --source winget --accept-package-agreements --accept-source-agreements --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.NativeDesktop --add Microsoft.VisualStudio.Component.VC.CLI.Support --add Microsoft.Net.Component.4.8.TargetingPack --includeRecommended"
```

- `NativeDesktop` is "Desktop development with C++" (compiler, Windows SDK)
- `VC.CLI.Support` is the C++/CLI component

Check:

```powershell
& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -products * -requires Microsoft.VisualStudio.Component.VC.CLI.Support -property installationPath
```

## 3. Clone

```powershell
git clone --branch python-port https://github.com/jamiemc1/MHP3-ASS.git $HOME\Documents\MHP3-ASS
```

Git Credential Manager (bundled with Git for Windows) opens a browser for
GitHub login the first time you push from the Dell.

## 4. Build the original GUI

```powershell
powershell -ExecutionPolicy Bypass -File $HOME\Documents\MHP3-ASS\scripts\windows\build-legacy.ps1
```

The script finds MSBuild through `vswhere` and passes property overrides that
retarget the 2017-era project (v141 toolset, Windows 8.1 SDK) to VS 2022,
**without editing any file in `legacy/`**. If you open the solution in the
IDE, don't accept the "Retarget projects" prompt: that rewrites the
`.vcxproj`.

Output: `legacy\Release\Athena's ASS MHP3rd.exe`.

## 5. Run it (at the Dell)

GUI programs started over SSH can't show a window on the desktop, so launch
this from a PowerShell window on the Dell itself. The application loads
`Data\...` relative to the current directory, so start it from `legacy\Run`:

```powershell
cd $HOME\Documents\MHP3-ASS\legacy\Run
& "..\Release\Athena's ASS MHP3rd.exe"
```

**Careful:** adding charms in the GUI writes to `legacy\Run\Data\mycharms.txt`,
which is a tracked file. To have git ignore your local edits:

```powershell
git update-index --skip-worktree legacy/Run/Data/mycharms.txt
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Add-WindowsCapability` throws `COMException` | Use the `winget install Microsoft.OpenSSH.Preview` route above |
| Port 22 times out from the Mac | `Get-Service sshd` (running?) and the firewall rule above |
| `Permission denied (publickey)` | Check `ssh-keygen -lf` and `icacls` on `administrators_authorized_keys`. For a definitive reason: `Stop-Service sshd; sshd -d`, connect once, read the output, `Start-Service sshd` |
| `MSB8020: The build tools for v141 cannot be found` | MSBuild ran without the script's `/p:PlatformToolset=v143` |
| `C++/CLI support is not installed` | Add the "C++/CLI support for v143 build tools" component |
| `The reference assemblies for .NETFramework,Version=... were not found` | Install that targeting pack, or keep `/p:TargetFrameworkVersion=v4.8` |
| GUI starts with empty lists or crashes on start | It wasn't started from `legacy\Run` |
