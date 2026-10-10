# Installation Guide

[日本語](INSTALL.md) | **English**

Setup steps required to run chappy.

## 1. Install uv

chappy uses the Python package manager [uv](https://docs.astral.sh/uv/).
Install it with the steps below.

### Windows

Open PowerShell and run:

```powershell
winget install --id=astral-sh.uv -e
```

### macOS / Linux

Open a terminal and run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal after installation completes,
or follow the PATH instructions printed by the installer.

### Other installation methods

For installation methods other than the above, see the official documentation:

- [uv Installation Guide](https://docs.astral.sh/uv/getting-started/installation/)

## 2. Run chappy

**Windows:**

1. Open the `scripts` folder in Explorer
2. Double-click `run.cmd`

Or from the command prompt:

```cmd
scripts\run.cmd
```

A security warning may appear on the first run.
See "[3.1 If a security warning appears](#31-if-a-security-warning-appears)" for how to resolve it.

**macOS:**

1. Open the `scripts` folder in Finder
2. Double-click `run.command`

On the first run, macOS may warn that the developer cannot be verified.
In that case, Control-click the file and choose "Open".

Or from the terminal:

```bash
./scripts/run.sh
```

**Linux:**

Run the following in a terminal:

```bash
./scripts/run.sh
```

To register chappy in your application menu, run this once:

```bash
./scripts/install-desktop.sh
```

---

On the first run, the required Python version and dependencies are downloaded and installed automatically.

## 3. Notes for Windows

### 3.1 If a security warning appears

**"The publisher could not be verified"**

Windows records that a downloaded file came from another computer, and extracting the zip
passes that record on to its contents. Clear it from `run.cmd`.

1. Right-click `run.cmd` in the `scripts` folder and open "Properties"
2. Tick **"Unblock"** next to "Security: This file came from another computer..." at the
   bottom of the General tab
3. Click "Apply", then "OK"
4. Double-click `run.cmd` again

**Blocked by Smart App Control**

If that does not help, this feature is blocking the Python that chappy uses. It refuses any
executable without a digital signature, so this is not specific to chappy.

You need to turn it off to run chappy. Open "Settings > Privacy & security > Windows Security >
App & browser control > Smart App Control settings" and select "Off".

Before you do:

- **Turning it back on will stop chappy from starting again.** Leave it off while you use chappy
- Some Windows protection is weakened while it is off
- On Windows versions older than the April 2026 update, turning it off is permanent unless you
  reset Windows. Install pending Windows updates first

### 3.2 Path length limit

Windows has traditionally imposed a 260-character path length limit.
If chappy is placed in a deeply nested folder, installing dependencies may fail.

Place chappy under a **short path**:

- ✓ `C:\chappy`
- ✓ `D:\projects\chappy`
- ✗ `C:\Users\Username\Documents\Research\2024\Projects\Astronomy\chappy`

## 4. Uninstallation

chappy does not use an installer, so removal is manual.
Quit chappy before you start (a running instance writes its settings back on exit).

### 4.1 The application itself

Delete the folder where you placed chappy.
The `.venv` / `.uv` directories generated at run time are removed with it.

### 4.2 User data (`~/.chappy/`)

| File / directory | Contents |
| --- | --- |
| `presets.json` | Absorption line presets |
| `config.toml` | Language setting |
| `spectral_lines.csv` | Replacement spectral line catalog (only if you placed one) |
| `log/` | Application logs |

```bash
rm -rf ~/.chappy          # macOS / Linux
```

```powershell
Remove-Item -Recurse -Force "$HOME\.chappy"   # Windows
```

If you set `CHAPPY_CONFIG_DIR` / `CHAPPY_LOG_DIR` / `CHAPPY_SPECTRAL_LINES_CSV`, remove the
directories you pointed them at instead of `~/.chappy`.

### 4.3 GUI settings such as window state

Window size, splitter positions, and the last opened folder are stored in the
OS-native settings area. chappy uses two settings stores, so remove both.

**macOS:**

```bash
defaults delete com.chappy-astronomy.chappy
defaults delete com.chappy.Chappy
```

**Windows:** delete these keys with the Registry Editor.

- `HKEY_CURRENT_USER\Software\chappy\chappy`
- `HKEY_CURRENT_USER\Software\Chappy\Chappy`

**Linux:**

```bash
rm -f ~/.config/chappy/chappy.conf ~/.config/Chappy/Chappy.conf
```

### 4.4 Desktop entry (Linux only)

Remove this only if you ran `scripts/install-desktop.sh`.

```bash
rm -f ~/.local/share/applications/chappy.desktop
```
