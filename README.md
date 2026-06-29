# Digital Pavement Condition Evaluation and Maintenance Decision Tool
TCG633 — Bridge & Road Maintenance | Individual Project

## What's in this folder
- `app.py` — the Streamlit application (the UI)
- `pavement_logic.py` — the PCI/IRI/Hybrid calculation engine (the engineering logic)
- `sample_data/pci_input.csv` and `sample_data/iri_input.csv` — your 10-section dataset, loaded automatically when the app starts
- `requirements.txt` — list of Python packages needed

## How to run this on your own computer

### Step 1 — Install Python (if you don't already have it)
Download from https://www.python.org/downloads/ (3.9 or newer). During install on
Windows, tick "Add Python to PATH".

### Step 2 — Open a terminal in this folder
- Windows: open the folder, click the address bar, type `cmd`, press Enter
- Mac: right-click the folder → "New Terminal at Folder" (or use Terminal + `cd`)

### Step 3 — Install the required packages
```
pip install -r requirements.txt
```

### Step 4 — Run the app
```
streamlit run app.py
```

A browser tab will open automatically (usually at `http://localhost:8501`). If it
doesn't, copy the URL shown in the terminal into your browser.

### Step 5 — Stop the app
Go back to the terminal and press `Ctrl+C`.

## Using the tool

1. **Sidebar** — choose evaluation mode (PCI / IRI / Hybrid) and data source
   (built-in dataset, or upload your own Excel/CSV)
2. **Data Input tab** — view and edit the defect/roughness data directly in the
   tables; rows can be added, edited, or removed
3. **Computation & Results tab** — see PCI/IRI/Hybrid scores, condition
   classification, and maintenance recommendations per section; download as CSV
4. **Dashboard tab** — bar chart of scores by section, pie chart of condition
   distribution, and a flagged list of sections needing priority attention
5. **Methodology tab** — the formulas and condition bands used, useful to have
   open while explaining the tool in your report or video

## Tip for your video demo
In the Data Input tab, try editing a defect's Severity (e.g. Low → High) or
Area Affected (%) for one section, then switch to the Results or Dashboard tab
to show the numbers and chart updating live. This is a strong way to
demonstrate the tool is genuinely functional, not just displaying static results.

## If something goes wrong
- **"streamlit: command not found"** — try `python -m streamlit run app.py` instead
- **Module not found errors** — re-run `pip install -r requirements.txt`
- **Uploaded Excel not recognized** — make sure the file has sheets literally
  named `PCI_Input` and `IRI_Input` with a `Section ID` column (this matches
  the dataset file you were given)
