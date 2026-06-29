"""
Core pavement evaluation logic for the Digital Pavement Condition Evaluation Tool.
TCG633 - Bridge and Road Maintenance

This module contains the engineering calculations, kept separate from the
Streamlit UI so the logic can be tested independently and is easy to explain
in the technical report / video.
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Default lookup tables (editable via the app's sidebar)
# Based on the lecturer-provided template, simplified from ASTM D6433's
# curve-based deduct values into a linear weighted formula for course use.
# ---------------------------------------------------------------------------

DEFAULT_DEFECT_WEIGHTS = {
    "Longitudinal Crack": 1.0,
    "Alligator (Fatigue) Crack": 1.6,
    "Potholes": 2.2,
    "Raveling": 1.2,
    "Depression/Sag": 1.4,
    "Patching (Failed)": 1.8,
    "Bleeding/Flushing": 1.0,
    "Rut/Rutting": 1.6,
}

DEFAULT_SEVERITY_FACTORS = {
    "Low": 0.6,
    "Medium": 1.0,
    "High": 1.4,
}

DEFAULT_PCI_BANDS = [
    # (min, max, condition class, recommended maintenance)
    (85, 100, "Very Good", "Routine maintenance (cleaning, grass cutting, minor touch-ups)"),
    (70, 85, "Good", "Preventive maintenance (crack sealing, local patching)"),
    (55, 70, "Fair", "Surface treatment / Overlay (localized)"),
    (0, 55, "Poor", "Major rehabilitation / Reconstruction assessment"),
]

DEFAULT_IRI_BANDS = [
    (0, 2, "Very Good (Smooth)", "Routine maintenance"),
    (2, 3, "Good", "Preventive maintenance (localized patching/leveling)"),
    (3, 4, "Fair", "Surface treatment / thin overlay"),
    (4, 9999, "Poor (Rough)", "Structural overlay / rehabilitation"),
]

# Ordering used to decide which condition is "worse" for the Hybrid index.
# Lower index = better condition.
CONDITION_RANK = ["Very Good", "Good", "Fair", "Poor"]


def classify(value: float, bands: list) -> tuple:
    """Return (condition_class, recommendation) for a value given a band list.
    Bands are checked from best to worst; value falls in [min, max)."""
    for mn, mx, cls, rec in bands:
        if mn <= value < mx:
            return cls, rec
    # Edge case: value exactly equals the top of the best band (e.g. PCI = 100)
    last_mn, last_mx, last_cls, last_rec = bands[0]
    if value >= last_mn:
        return last_cls, last_rec
    # Fallback: worst band
    cls, rec = bands[-1][2], bands[-1][3]
    return cls, rec


def normalize_condition_label(label: str) -> str:
    """Map IRI labels like 'Very Good (Smooth)' to the common 4-class scale."""
    for base in CONDITION_RANK:
        if label.startswith(base):
            return base
    return label


def compute_pci(pci_input_df: pd.DataFrame,
                 defect_weights: dict = None,
                 severity_factors: dict = None,
                 pci_bands: list = None) -> pd.DataFrame:
    """
    Compute PCI per section from raw defect input data.

    pci_input_df columns required: 'Section ID', 'Defect Type', 'Severity',
    'Area Affected (%)'

    Returns a DataFrame with one row per Section ID:
    Section ID, Sum Deduct, PCI, PCI Condition, PCI Recommendation
    """
    defect_weights = defect_weights or DEFAULT_DEFECT_WEIGHTS
    severity_factors = severity_factors or DEFAULT_SEVERITY_FACTORS
    pci_bands = pci_bands or DEFAULT_PCI_BANDS

    df = pci_input_df.dropna(subset=["Section ID", "Defect Type", "Severity", "Area Affected (%)"]).copy()
    if df.empty:
        return pd.DataFrame(columns=["Section ID", "Sum Deduct", "PCI", "PCI Condition", "PCI Recommendation"])

    df["Weighting Factor"] = df["Defect Type"].map(defect_weights)
    df["Severity Factor"] = df["Severity"].map(severity_factors)
    df["Deduct Value"] = df["Weighting Factor"] * df["Severity Factor"] * df["Area Affected (%)"]

    summary = df.groupby("Section ID", as_index=False)["Deduct Value"].sum()
    summary = summary.rename(columns={"Deduct Value": "Sum Deduct"})
    summary["PCI"] = (100 - summary["Sum Deduct"]).clip(lower=0).round(1)

    results = summary["PCI"].apply(lambda v: classify(v, pci_bands))
    summary["PCI Condition"] = results.apply(lambda r: r[0])
    summary["PCI Recommendation"] = results.apply(lambda r: r[1])

    return summary.sort_values("Section ID").reset_index(drop=True)


def compute_iri(iri_input_df: pd.DataFrame,
                 iri_bands: list = None) -> pd.DataFrame:
    """
    Compute average IRI per section from segment-level readings.

    iri_input_df columns required: 'Section ID', 'IRI (m/km)'

    Returns a DataFrame with one row per Section ID:
    Section ID, Avg IRI (m/km), IRI Condition, IRI Recommendation
    """
    iri_bands = iri_bands or DEFAULT_IRI_BANDS

    df = iri_input_df.dropna(subset=["Section ID", "IRI (m/km)"]).copy()
    if df.empty:
        return pd.DataFrame(columns=["Section ID", "Avg IRI (m/km)", "IRI Condition", "IRI Recommendation"])

    summary = df.groupby("Section ID", as_index=False)["IRI (m/km)"].mean()
    summary["Avg IRI (m/km)"] = summary["IRI (m/km)"].round(2)
    summary = summary.drop(columns=["IRI (m/km)"])

    results = summary["Avg IRI (m/km)"].apply(lambda v: classify(v, iri_bands))
    summary["IRI Condition"] = results.apply(lambda r: normalize_condition_label(r[0]))
    summary["IRI Recommendation"] = results.apply(lambda r: r[1])

    return summary.sort_values("Section ID").reset_index(drop=True)


def compute_hybrid(pci_summary: pd.DataFrame, iri_summary: pd.DataFrame,
                    pci_bands: list = None, iri_bands: list = None) -> pd.DataFrame:
    """
    Merge PCI and IRI results per section and compute a Hybrid condition:
    the MORE CONSERVATIVE (worse) of the two classifications, per standard
    engineering judgment (visual defects and roughness can disagree; the
    worse-condition reading should drive the maintenance decision).
    """
    pci_bands = pci_bands or DEFAULT_PCI_BANDS
    iri_bands = iri_bands or DEFAULT_IRI_BANDS

    merged = pd.merge(pci_summary, iri_summary, on="Section ID", how="outer").sort_values("Section ID")

    def worse_of(pci_cond, iri_cond):
        if pd.isna(pci_cond) and pd.isna(iri_cond):
            return None
        if pd.isna(pci_cond):
            return iri_cond
        if pd.isna(iri_cond):
            return pci_cond
        rank_pci = CONDITION_RANK.index(pci_cond) if pci_cond in CONDITION_RANK else 0
        rank_iri = CONDITION_RANK.index(iri_cond) if iri_cond in CONDITION_RANK else 0
        return pci_cond if rank_pci >= rank_iri else iri_cond

    merged["Hybrid Condition"] = merged.apply(
        lambda r: worse_of(r.get("PCI Condition"), r.get("IRI Condition")), axis=1
    )

    # Recommendation follows the hybrid condition, sourced from whichever
    # index produced that worse classification, falling back to PCI bands.
    rec_lookup = {cls: rec for _, _, cls, rec in pci_bands}
    rec_lookup_iri = {normalize_condition_label(cls): rec for _, _, cls, rec in iri_bands}

    def hybrid_rec(cond, pci_cond, iri_cond, pci_rec, iri_rec):
        if cond == pci_cond:
            return pci_rec
        if cond == iri_cond:
            return iri_rec
        return rec_lookup.get(cond, "")

    merged["Hybrid Recommendation"] = merged.apply(
        lambda r: hybrid_rec(
            r.get("Hybrid Condition"), r.get("PCI Condition"), r.get("IRI Condition"),
            r.get("PCI Recommendation"), r.get("IRI Recommendation")
        ), axis=1
    )

    return merged.reset_index(drop=True)


def bands_to_dataframe(bands: list, value_label: str) -> pd.DataFrame:
    """Helper to display a band list as an editable dataframe in the UI."""
    return pd.DataFrame(bands, columns=[f"{value_label} Min", f"{value_label} Max", "Condition Class", "Recommended Maintenance"])


def dataframe_to_bands(df: pd.DataFrame) -> list:
    """Helper to convert an edited dataframe back into a band list."""
    return [tuple(row) for row in df.itertuples(index=False, name=None)]
