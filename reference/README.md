
# Walmart Outlook Importer — Step 1

This is the first step of your pipeline. It:

- Connects to Outlook (desktop) via COM (pywin32).
- Finds the folder: `luis.rodrigues.oliveira@outlook.com/Inbox/Shopping/Supermarkets/Walmart`.
- Prints two lines:
  1) Connection success/failure
  2) Folder found + number of emails OR not found

We'll expand this project step-by-step.

## Prereqs
- Windows with Outlook desktop installed and configured for your account.
- Python 3.9+ installed and available as `py` or `python` on PATH.

## Install
Open **PowerShell** in this folder and run:

```
.\installer.ps1
```

This will create a local virtual environment `.venv` and install the Python package `pywin32`.

## Run
From PowerShell, inside the folder:

```
.\.venv\Scripts\Activate.ps1
py .\main.py --period 2025-10
```

or

```
python .\main.py --period 2025-10
```

### What you should see
- A line about Outlook connection status.
- A line about whether the folder was found and how many items are in it.

## Folder path notes
The folder path is parsed as
`<store>/<root>/<subfolder 1>/<subfolder 2>/...`

For you:
`luis.rodrigues.oliveira@outlook.com/Inbox/Shopping/Supermarkets/Walmart`

If your actual store display name differs in Outlook (e.g., the mailbox shows as `Outlook` or `Luis Rodrigues Oliveira`), update the `TARGET_FOLDER_PATH` constant in `main.py` accordingly.
