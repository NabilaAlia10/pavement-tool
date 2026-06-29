"""
Digital Pavement Condition Evaluation and Maintenance Decision Tool
TCG633 - Bridge and Road Maintenance | Individual Project

Run with:  streamlit run app.py
"""

import io
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from pavement_logic import (
    DEFAULT_DEFECT_WEIGHTS, DEFAULT_SEVERITY_FACTORS,
    DEFAULT_PCI_BANDS, DEFAULT_IRI_BANDS,
    compute_pci, compute_iri, compute_hybrid,
    bands_to_dataframe, dataframe_to_bands,
)

# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pavement Condition Evaluation Tool",
    page_icon="🛣️",
    layout="wide",
)

CONDITION_COLORS = {
    "Very Good": "#2E7D32",
    "Good": "#9E9D24",
    "Fair": "#F57C00",
    "Poor": "#C62828",
}

st.markdown("""
<style>
    .block-container {padding-top: 2rem;}
    .condition-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-weight: 600; font-size: 0.85rem; color: white;
    }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    h1, h2, h3 { font-family: 'Source Sans Pro', sans-serif; }
</style>
""", unsafe_allow_html=True)


def colored_condition_table(df: pd.DataFrame, cond_cols: list) -> "pd.io.formats.style.Styler":
    """Apply background color to condition columns for visual scanning."""
    def style_cond(val):
        base = str(val).split(" ")[0] if val else ""
        for k in CONDITION_COLORS:
            if str(val).startswith(k):
                color = CONDITION_COLORS[k]
                return f"background-color: {color}22; color: {color}; font-weight: 600;"
        return ""
    sty = df.style
    for c in cond_cols:
        if c in df.columns:
            sty = sty.applymap(style_cond, subset=[c])
    return sty


# ---------------------------------------------------------------------------
# Sidebar: data source, mode, lookup editing
# ---------------------------------------------------------------------------
st.sidebar.title("🛣️ Tool Controls")

st.sidebar.subheader("1. Data Source")
data_source = st.sidebar.radio(
    "Choose data source",
    ["Use built-in sample dataset", "Upload my own file"],
    index=0,
)

uploaded_file = None
if data_source == "Upload my own file":
    uploaded_file = st.sidebar.file_uploader(
        "Upload Excel (.xlsx) with 'PCI_Input' and 'IRI_Input' sheets, or two CSVs",
        type=["xlsx", "csv"],
    )

st.sidebar.subheader("2. Evaluation Mode")
mode = st.sidebar.radio("Select mode", ["PCI", "IRI", "Hybrid (PCI + IRI)"], index=2)

with st.sidebar.expander("3. Edit Lookup Tables (advanced)"):
    st.caption("Adjust weighting/severity factors and condition bands to match your standard.")
    edit_lookup = st.checkbox("Enable lookup editing", value=False)

st.sidebar.markdown("---")
st.sidebar.caption("TCG633 Bridge & Road Maintenance — Individual Project")
st.sidebar.caption("Digital Pavement Condition Evaluation and Maintenance Decision Tool")


# ---------------------------------------------------------------------------
# Load default sample data
# ---------------------------------------------------------------------------
@st.cache_data
def load_default_data():
    pci = pd.read_csv("sample_data/pci_input.csv")
    iri = pd.read_csv("sample_data/iri_input.csv")
    return pci, iri


def _find_header_row(xls, sheet_name, key_col="Section ID", scan_rows=10):
    """Find the row index containing the real column headers, since our
    dataset sheets have title/subtitle rows above the header."""
    preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=scan_rows)
    for i, row in preview.iterrows():
        if key_col in row.values:
            return i
    return 0


def load_uploaded_data(file):
    if file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(file)
        pci_header = _find_header_row(xls, "PCI_Input")
        iri_header = _find_header_row(xls, "IRI_Input")
        pci = pd.read_excel(xls, sheet_name="PCI_Input", header=pci_header)
        iri = pd.read_excel(xls, sheet_name="IRI_Input", header=iri_header)
        # Drop any stray fully-blank rows and ensure Section ID is numeric
        pci = pci[pd.to_numeric(pci["Section ID"], errors="coerce").notna()]
        iri = iri[pd.to_numeric(iri["Section ID"], errors="coerce").notna()]
        return pci, iri
    else:
        st.sidebar.warning("CSV upload: please upload PCI_Input first, then IRI_Input separately below.")
        return None, None


if data_source == "Upload my own file" and uploaded_file is not None:
    pci_input_raw, iri_input_raw = load_uploaded_data(uploaded_file)
    if pci_input_raw is None:
        st.stop()
else:
    pci_input_raw, iri_input_raw = load_default_data()

if "pci_input" not in st.session_state:
    st.session_state.pci_input = pci_input_raw.copy()
if "iri_input" not in st.session_state:
    st.session_state.iri_input = iri_input_raw.copy()

# Reset session data if a new file is uploaded
if data_source == "Upload my own file" and uploaded_file is not None:
    if st.sidebar.button("Reload uploaded data"):
        st.session_state.pci_input = pci_input_raw.copy()
        st.session_state.iri_input = iri_input_raw.copy()


# ---------------------------------------------------------------------------
# Lookup table state
# ---------------------------------------------------------------------------
if "defect_weights" not in st.session_state:
    st.session_state.defect_weights = DEFAULT_DEFECT_WEIGHTS.copy()
if "severity_factors" not in st.session_state:
    st.session_state.severity_factors = DEFAULT_SEVERITY_FACTORS.copy()
if "pci_bands" not in st.session_state:
    st.session_state.pci_bands = DEFAULT_PCI_BANDS.copy()
if "iri_bands" not in st.session_state:
    st.session_state.iri_bands = DEFAULT_IRI_BANDS.copy()

if edit_lookup:
    with st.sidebar.expander("Defect Weighting Factors", expanded=False):
        for k in list(st.session_state.defect_weights.keys()):
            st.session_state.defect_weights[k] = st.number_input(
                k, value=float(st.session_state.defect_weights[k]), step=0.1, key=f"w_{k}"
            )
    with st.sidebar.expander("Severity Factors", expanded=False):
        for k in list(st.session_state.severity_factors.keys()):
            st.session_state.severity_factors[k] = st.number_input(
                k, value=float(st.session_state.severity_factors[k]), step=0.1, key=f"s_{k}"
            )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🛣️ Digital Pavement Condition Evaluation and Maintenance Decision Tool")
st.caption(
    "District JKR Maintenance Division — Secondary Road Network Assessment "
    "| PCI (ASTM D6433-based) & IRI (Roughness) Evaluation"
)

tab_input, tab_results, tab_dashboard, tab_about = st.tabs(
    ["📥 Data Input", "📊 Computation & Results", "📈 Dashboard", "ℹ️ Methodology"]
)

# ---------------------------------------------------------------------------
# TAB 1: Data Input
# ---------------------------------------------------------------------------
with tab_input:
    st.subheader("Pavement Condition Input Data")
    st.caption("Edit values directly in the tables below. Changes apply immediately to the results.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**PCI Input — Defect Records**")
        st.session_state.pci_input = st.data_editor(
            st.session_state.pci_input,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Defect Type": st.column_config.SelectboxColumn(
                    options=list(st.session_state.defect_weights.keys())
                ),
                "Severity": st.column_config.SelectboxColumn(
                    options=list(st.session_state.severity_factors.keys())
                ),
                "Area Affected (%)": st.column_config.NumberColumn(min_value=0, max_value=100, step=0.1),
            },
            key="pci_editor",
        )
    with col2:
        st.markdown("**IRI Input — Roughness Readings**")
        st.session_state.iri_input = st.data_editor(
            st.session_state.iri_input,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "IRI (m/km)": st.column_config.NumberColumn(min_value=0, max_value=20, step=0.01),
            },
            key="iri_editor",
        )

    st.info(
        "💡 Tip for demo: try changing a Severity or Area Affected (%) value above, "
        "then check the Results and Dashboard tabs — they update instantly."
    )


# ---------------------------------------------------------------------------
# Compute results (used by Results + Dashboard tabs)
# ---------------------------------------------------------------------------
pci_summary = compute_pci(
    st.session_state.pci_input,
    defect_weights=st.session_state.defect_weights,
    severity_factors=st.session_state.severity_factors,
    pci_bands=st.session_state.pci_bands,
)
iri_summary = compute_iri(st.session_state.iri_input, iri_bands=st.session_state.iri_bands)
hybrid_summary = compute_hybrid(pci_summary, iri_summary,
                                 pci_bands=st.session_state.pci_bands,
                                 iri_bands=st.session_state.iri_bands)

# ---------------------------------------------------------------------------
# TAB 2: Computation & Results
# ---------------------------------------------------------------------------
with tab_results:
    st.subheader(f"Results — {mode} Mode")

    if mode == "PCI":
        display_df = pci_summary.rename(columns={"PCI Recommendation": "Maintenance Recommendation"})
        cond_col = ["PCI Condition"]
    elif mode == "IRI":
        display_df = iri_summary.rename(columns={"IRI Recommendation": "Maintenance Recommendation"})
        cond_col = ["IRI Condition"]
    else:
        display_df = hybrid_summary[[
            "Section ID", "PCI", "PCI Condition", "Avg IRI (m/km)", "IRI Condition",
            "Hybrid Condition", "Hybrid Recommendation"
        ]].rename(columns={"Hybrid Recommendation": "Maintenance Recommendation"})
        cond_col = ["PCI Condition", "IRI Condition", "Hybrid Condition"]

    st.dataframe(
        colored_condition_table(display_df, cond_col),
        use_container_width=True,
        height=min(45 * (len(display_df) + 1), 450),
    )

    # Quick stats row
    final_cond_col = "Hybrid Condition" if mode.startswith("Hybrid") else cond_col[0]
    counts = display_df[final_cond_col].value_counts()
    cols = st.columns(4)
    for i, band in enumerate(["Very Good", "Good", "Fair", "Poor"]):
        n = int(counts.get(band, 0))
        cols[i].metric(band, n, help=f"{n} of {len(display_df)} sections")

    csv_buf = io.StringIO()
    display_df.to_csv(csv_buf, index=False)
    st.download_button(
        "⬇️ Download Results as CSV",
        csv_buf.getvalue(),
        file_name=f"pavement_results_{mode.split()[0].lower()}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# TAB 3: Dashboard
# ---------------------------------------------------------------------------
with tab_dashboard:
    st.subheader("Network Condition Dashboard")

    if mode == "PCI":
        value_col, cond_col, label = "PCI", "PCI Condition", "PCI"
        chart_df = pci_summary
    elif mode == "IRI":
        value_col, cond_col, label = "Avg IRI (m/km)", "IRI Condition", "IRI (m/km)"
        chart_df = iri_summary
    else:
        value_col, cond_col, label = "PCI", "Hybrid Condition", "Hybrid (worse of PCI/IRI)"
        chart_df = hybrid_summary

    c1, c2 = st.columns([3, 2])

    with c1:
        bar = px.bar(
            chart_df, x="Section ID", y=value_col, color=cond_col,
            color_discrete_map=CONDITION_COLORS,
            title=f"{label} by Section",
            text=value_col,
        )
        bar.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        bar.update_layout(xaxis=dict(dtick=1), showlegend=True)
        st.plotly_chart(bar, use_container_width=True)

    with c2:
        pie_counts = chart_df[cond_col].value_counts().reset_index()
        pie_counts.columns = ["Condition", "Count"]
        pie = px.pie(
            pie_counts, names="Condition", values="Count",
            color="Condition", color_discrete_map=CONDITION_COLORS,
            title="Condition Distribution", hole=0.45,
        )
        st.plotly_chart(pie, use_container_width=True)

    if mode.startswith("Hybrid"):
        st.markdown("**PCI vs IRI Comparison per Section**")
        comp = go.Figure()
        comp.add_trace(go.Scatter(
            x=hybrid_summary["Section ID"], y=hybrid_summary["PCI"],
            mode="lines+markers", name="PCI (0-100 scale)"
        ))
        comp.add_trace(go.Scatter(
            x=hybrid_summary["Section ID"], y=hybrid_summary["Avg IRI (m/km)"] * 20,
            mode="lines+markers", name="IRI x20 (scaled for comparison)"
        ))
        comp.update_layout(xaxis_title="Section ID", yaxis_title="Score (scaled)",
                            title="Do PCI and IRI agree on condition across sections?")
        st.plotly_chart(comp, use_container_width=True)
        st.caption(
            "When PCI and IRI disagree on a section's condition, the Hybrid Index takes "
            "the more conservative (worse) classification — prioritizing road user safety."
        )

    st.markdown("**Sections Needing Priority Attention**")
    priority = chart_df[chart_df[cond_col].isin(["Poor"])]
    if priority.empty:
        st.success("No sections currently classified as Poor.")
    else:
        st.warning(f"{len(priority)} section(s) classified as Poor — recommend prioritizing in next maintenance cycle.")
        st.dataframe(priority, use_container_width=True)


# ---------------------------------------------------------------------------
# TAB 4: Methodology / About
# ---------------------------------------------------------------------------
with tab_about:
    st.subheader("Methodology")

    st.markdown("""
**Pavement Condition Index (PCI)**

For each defect observed in a section:

```
Deduct Value = Weighting Factor × Severity Factor × Area Affected (%)
```

All deduct values in a section are summed, then:

```
PCI = 100 − (Sum of Deduct Values), floored at 0
```

This is a linear simplification of ASTM D6433's curve-based deduct value
method, adapted for course use. The full standard uses non-linear deduct
curves per defect type and a Corrected Deduct Value (CDV) process to avoid
double-penalizing sections with many simultaneous defects.

**International Roughness Index (IRI)**

```
Section IRI = Average of segment-level IRI readings (m/km)
```

**Hybrid Index**

Combines PCI and IRI by selecting the more conservative (worse) of the two
classifications for each section — reflecting the engineering judgment that
either indicator showing poor condition is sufficient grounds for concern.
    """)

    st.markdown("**Condition Bands**")
    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("*PCI Bands*")
        st.table(bands_to_dataframe(st.session_state.pci_bands, "PCI"))
    with bc2:
        st.markdown("*IRI Bands*")
        st.table(bands_to_dataframe(st.session_state.iri_bands, "IRI"))

    st.markdown("**Defect Weighting Factors**")
    st.table(pd.DataFrame(
        list(st.session_state.defect_weights.items()),
        columns=["Defect Type", "Weighting Factor"]
    ))

    st.caption(
        "References: ASTM D6433 (PCI Survey Standard); JKR Pavement Maintenance Manual; "
        "JKR IRI Classification Guidance."
    )
