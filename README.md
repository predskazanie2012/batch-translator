# Batch Translator

Batch Translator processes folders of TXT and Word documents across multiple languages. Desktop and web interfaces share the same translation engine, with per-file progress and separate output folders for each target language.

## Features

- Translate batches of TXT and DOCX documents.
- Choose supported languages and translation engines.
- Follow per-file progress without blocking the interface.
- Reuse the same translation core from desktop, web and pipeline integrations.

## How it works

A shared BatchTranslator core handles file reading and translation. Thin Flask and Tkinter interfaces present the same workflow.

**Stack:** Python · Flask · Tkinter · python-docx · Google Cloud / DeepL

## Getting started

Use Python 3.12 and a separate virtual environment. Run the following commands from this repository's root in Windows PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-local.txt
```

The local requirements include both supported provider clients. Configure your own Google Cloud credentials or `DEEPL_API_KEY` in the ignored local `.env`. Translation sends document text to the selected provider.

If you need provider credentials, copy `.env.example` to `.env` and configure only the services you use. Keep `.env` local.

### Start the application

Open http://127.0.0.1:5100. Run `python main.py` for the desktop UI. Configure an optional DeepL key in .env; translation requires access to the chosen service.

```powershell
python app.py
```

## Example workflow

Translate a short TXT file and a small DOCX into one target language, then inspect the text, paragraphs and table cells.

## Testing and limitations

TXT and DOCX files were written and reopened using deterministic provider responses; paragraphs, basic bold styling and table cells were checked. Live translation quality and provider connectivity were not tested.

See [Verification](VERIFICATION.md) for the recorded checks and [Limitations](LIMITATIONS.md) for integration requirements.

## Configuration and security

Keep web services bound to `127.0.0.1`. Hosting this application for multiple users requires authentication and separate storage and resource limits. Configure your own provider credentials when a feature requires them; credentials and personal data are not included. See [Security](SECURITY.md) for local configuration and reporting guidance.
