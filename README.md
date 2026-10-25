<<<<<<< HEAD
::: {align="center"}
`<img src="ALIRA_ULTRA_APP/tabbu_modules/assets/alira_logo.png" alt="ALIRA logo" width="120" />`{=html}

\# ALIRA ULTRA

**Your personal AI assistant for voice, vision, PC control, chat, and
AI-assisted website building.**

*Speak to ALIRA, ask questions, work with files, and use supported
desktop tools from one interface.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)](https://www.microsoft.com/windows)
[![AI](https://img.shields.io/badge/AI-Google%20Gemini-4285F4)](https://ai.google.dev/)
:::

------------------------------------------------------------------------

## About

**ALIRA ULTRA** is a customized desktop AI assistant project. This
repository contains local changes and branding built on top of the
upstream **MYRA ULTRA** project.

-   **This customized project:** ALIRA ULTRA
-   **Upstream project:** [MYRA
    ULTRA](https://github.com/codeninjavik/myra-ultra)
-   **Upstream creator:** [Vikash Kumar
    (@codeninjavik)](https://github.com/codeninjavik)
-   **ALIRA project maintainer:** [Md Ali /
    SecureWithAli](https://github.com/SecureWithAli)

This is an independent customization and is not the original MYRA ULTRA
repository. Please review the upstream license and preserve all required
copyright and license notices when redistributing code.

## Features

  -----------------------------------------------------------------------
  Area                                Description
  ----------------------------------- -----------------------------------
  Voice assistant                     Voice interaction through the
                                      configured Gemini Live integration

  Chat                                Text chat and supported image/file
                                      workflows

  PC controls                         Supported actions such as opening
                                      apps, screenshots, clipboard,
                                      volume, brightness, and window
                                      management

  Vision                              Camera vision and screen sharing,
                                      where dependencies and devices are
                                      available

  Files and documents                 Supported PDF, Word, Excel,
                                      PowerPoint, QR-code, and OCR
                                      workflows

  Web and media                       Supported search and media
                                      integrations

  System monitoring                   CPU, memory, storage, and battery
                                      information where supported

  Floating assistant UI               Floating orb and visual listening
                                      indicators, if enabled in the build

  Website-building integrations       Optional AI coding /
                                      website-building integrations,
                                      depending on installed modules and
                                      credentials
  -----------------------------------------------------------------------

> **Note:** Feature availability depends on your operating system,
> installed dependencies, API access, and which optional modules are
> present. Not every feature is guaranteed to work in every environment.

## Repository layout

The exact layout can vary by checkout. The main Windows desktop
application is in `ALIRA_ULTRA_APP/`.

``` text
ALIRA-ULTRA/
├── ALIRA_ULTRA_APP/
│   ├── tabbu.py                 # Main application entry point
│   ├── tabbu_ui.py              # UI components (if included)
│   ├── alira_ui.py              # UI components (if included)
│   ├── camera_vision_module.py  # Camera / vision integration (if included)
│   └── ...
├── docs/
│   └── images/                  # README images (if included)
├── README.md
└── LICENSE                      # Include the applicable license file
```

## Requirements

For the Windows desktop app, you may need:

-   Windows 10 or Windows 11
-   Python 3.10 or a compatible version supported by the dependencies
-   A working microphone; a webcam is optional
-   A Google Gemini API key for Gemini-powered features
-   Additional packages listed in the project's `requirements.txt`
-   Optional tools such as Node.js or OCR software for the integrations
    that require them

## Setup on Windows

### 1. Clone your repository

Replace `YOUR_GITHUB_USERNAME` with your GitHub username:

``` powershell
git clone https://github.com/YOUR_GITHUB_USERNAME/ALIRA-Ultra.git
cd ALIRA-Ultra\ALIRA_ULTRA_APP
```

If your repository layout does not contain `ALIRA_ULTRA_APP`, navigate
to the folder that contains `tabbu.py` instead.

### 2. Create and activate a virtual environment

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the environment's Python
directly:

``` powershell
.\.venv\Scripts\python.exe --version
```

### 3. Install dependencies

If `requirements.txt` exists in the app folder:

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install optional dependencies only when the related feature is needed
and the package is documented for this project.

### 4. Configure the Gemini API key

Use the app's API-key dialog if available, or follow the configuration
method implemented by your local version.

If you use a `.env` file, keep real credentials out of Git. For example,
a local-only `.env` may contain:

``` env
GEMINI_API_KEY=replace_with_your_own_key
```

Never put a real API key, GitHub token, Vercel token, password, or other
secret in this README or commit it to the repository. If a key is
exposed, revoke it and create a replacement.

### 5. Run the app

From the directory containing `tabbu.py`:

``` powershell
python .\tabbu.py
```

## Optional integrations

Some versions of this project include integrations such as a website
builder, an AI coding agent, screen sharing, camera vision, OCR, and
deployment helpers.

-   Check the relevant subfolder's README or setup instructions before
    installing optional tools.
-   Install Node.js only if your selected integration requires it.
-   Configure deployment credentials locally and never commit them.
-   If a module is missing, the corresponding feature may be unavailable
    while the main app can still start.

## Troubleshooting

  -----------------------------------------------------------------------
  Problem                             Things to check
  ----------------------------------- -----------------------------------
  Gemini API key error                Verify the key, account access, and
                                      the local configuration method.
                                      Never post the key in an issue.

  Microphone does not work            Check Windows microphone privacy
                                      permissions and the selected input
                                      device.

  Camera does not capture             Check camera permissions, whether
                                      another app is using the webcam,
                                      and the app's camera logs.

  Screen sharing is unavailable       Check the optional screen-capture
                                      dependencies and the console
                                      message.

  Website builder / coder module is   Confirm the integration folder, its
  missing                             dependencies, and its setup
                                      instructions are present.

  `ModuleNotFoundError`               Activate the intended virtual
                                      environment and install the
                                      dependencies for that project
                                      version.
  -----------------------------------------------------------------------

## Credits and attribution

ALIRA ULTRA is a modified/customized project based on **MYRA ULTRA**.

-   **Original project:**
    [codeninjavik/myra-ultra](https://github.com/codeninjavik/myra-ultra)
-   **Original creator:** [Vikash Kumar
    (@codeninjavik)](https://github.com/codeninjavik)
-   **ALIRA project / maintainer profile:**
    [SecureWithAli](https://github.com/SecureWithAli)

The upstream project and its contributors deserve credit for the
original work. Changes specific to ALIRA should be documented in commit
history and project notes. Retain the upstream copyright and license
notices and include the applicable license text when required by the
upstream license.

## Contributing

Bug reports and improvements are welcome. Before opening a pull request:

1.  Describe the issue or change clearly.
2.  Avoid including API keys, access tokens, personal configuration, or
    private user data.
3.  Test the feature you changed.
4.  Include relevant logs with secrets removed.

## Security

Do not commit `.env` files, API keys, access tokens, passwords, private
configuration files, or personal data. If you accidentally publish a
secret, revoke it immediately and remove it from the repository history
as appropriate.

## License

Check the upstream repository's current `LICENSE` file and preserve the
applicable license and copyright notices. Do not add or claim a license
for files unless you have verified that you have the right to license
those files. If this repository includes code from multiple projects,
preserve each component's required notices and license terms.

------------------------------------------------------------------------

::: {align="center"}
Made with care by the ALIRA project maintainer, with attribution to the
original MYRA ULTRA project and its contributors.
:::
=======
# ALIRA-Ultra
ALIRA AI — A customized desktop assistant based on MYRA ULTRA.
>>>>>>> origin/main
