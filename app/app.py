# =============================================================================
# app.py
# Day 12: Streamlit Web Application
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This is the main entry point for the web application.
#   Run it with:  streamlit run app/app.py
#
# WHAT IS STREAMLIT?
#   Streamlit is a Python library that turns Python scripts into interactive
#   web applications. You write Python code and Streamlit renders it as HTML
#   in the browser -- no HTML, CSS, or JavaScript required.
#
#   Key concept: every time the user interacts with a widget (button, slider,
#   file uploader), Streamlit RERUNS the entire script from top to bottom.
#   State between reruns is preserved using st.session_state.
#
# HOW TO RUN:
#   1. cd to the project root
#   2. Activate venv:  .\venv\Scripts\activate
#   3. Run:            streamlit run app/app.py
#   4. Open browser:   http://localhost:8501
# =============================================================================

import os
import sys

# ── Add app/ to the Python path ───────────────────────────────────────────────
# When Streamlit runs this file, it may not know about our utils.py and
# predictor.py in the same directory. We explicitly add the directory of
# this file (app/) to sys.path so that "from utils import ..." works.

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)    # add app/ so we can import utils, predictor

# Now we can safely import our own modules
import numpy as np
import streamlit as st

from utils     import describe_features, validate_code
from predictor import (
    load_xgboost_model,
    load_rf_model,
    load_codebert_components,
    predict_with_model,
    demo_predict,
    XGB_MODEL_PATH,
    RF_MODEL_PATH,
)


# =============================================================================
# SECTION 1: PAGE CONFIGURATION
# =============================================================================
#
# st.set_page_config() MUST be the very first Streamlit call in the script.
# It sets browser tab title, icon, and layout.
#
# layout="wide" uses the full browser width instead of a narrow centered column.

st.set_page_config(
    page_title="Code Vulnerability Detector",
    page_icon="shield",           # browser tab icon (emoji or image path)
    layout="wide",                # use full screen width
    initial_sidebar_state="expanded",  # sidebar is open when app first loads
)


# =============================================================================
# SECTION 2: CUSTOM CSS STYLING
# =============================================================================
#
# st.markdown() with unsafe_allow_html=True lets us inject raw HTML/CSS.
# We use this to style the verdict box and metric cards beyond what
# Streamlit's built-in components support.

st.markdown("""
<style>
/* ── Verdict Box ──────────────────────────────────────────────────────────── */
.verdict-box {
    padding: 24px 32px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 20px;
    border: 2px solid rgba(255,255,255,0.15);
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.verdict-box h1 {
    font-size: 2.4rem;
    margin: 0 0 8px 0;
    font-weight: 800;
    letter-spacing: 2px;
}
.verdict-box h3 {
    font-size: 1.1rem;
    margin: 0;
    opacity: 0.9;
    font-weight: 500;
}

/* ── Metric Card ──────────────────────────────────────────────────────────── */
.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 18px 20px;
    text-align: center;
    margin: 6px 0;
}
.metric-card .value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #e8e8e8;
}
.metric-card .label {
    font-size: 0.82rem;
    color: #aaa;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Section Header ──────────────────────────────────────────────────────── */
.section-header {
    font-size: 1.15rem;
    font-weight: 600;
    color: #ccc;
    border-left: 4px solid #4e8ef7;
    padding-left: 12px;
    margin: 20px 0 10px 0;
}

/* ── Feature Table ───────────────────────────────────────────────────────── */
.feat-row {
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 0.88rem;
}
.feat-row:last-child { border-bottom: none; }
.feat-name  { color: #b0b0c0; }
.feat-value { color: #e0e0e0; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SECTION 3: CACHED MODEL LOADING
# =============================================================================
#
# @st.cache_resource is a decorator that tells Streamlit:
#   "Run this function ONCE and store the result in memory.
#    Every time the app reruns (due to user interaction), return the
#    cached result instead of running the function again."
#
# Without caching: CodeBERT (~500 MB) would reload every click (~60 seconds).
# With caching: CodeBERT loads once on startup and stays in memory.
#
# The difference from @st.cache_data:
#   @st.cache_resource  -- for heavy objects (models, DB connections)
#   @st.cache_data      -- for data frames, serialisable objects

@st.cache_resource(show_spinner=False)
def get_xgboost():
    """Load (and cache) the XGBoost model. Returns None if file not found."""
    return load_xgboost_model()

@st.cache_resource(show_spinner=False)
def get_rf():
    """Load (and cache) the Random Forest model. Returns None if file not found."""
    return load_rf_model()

@st.cache_resource(show_spinner=False)
def get_codebert():
    """
    Load (and cache) the CodeBERT tokenizer + model.
    This downloads ~500 MB on first run. Subsequent runs use the local cache.
    Returns (None, None) if transformers or torch is not available.
    """
    return load_codebert_components()


# =============================================================================
# SECTION 4: SIDEBAR
# =============================================================================
#
# st.sidebar is a special object -- anything rendered on it appears in the
# collapsible side panel on the left of the screen.

with st.sidebar:

    # ── Logo / Title ─────────────────────────────────────────────────────────
    st.markdown("## Code Vulnerability Detector")
    st.markdown("*Multi-Modal Detection using CodeBERT*")
    st.divider()   # st.divider() draws a horizontal line

    # ── About the Project ─────────────────────────────────────────────────────
    st.markdown("### About This Project")
    st.markdown("""
This tool analyses C source code functions for potential security
vulnerabilities using a **multi-modal machine learning** approach.

**Three analysis branches:**
- **AST Analysis** -- 11 structural features from the parse tree
- **Software Metrics** -- 13 code quality measurements
- **CodeBERT Embeddings** -- 768-dim semantic representation

**Feature fusion:** All 792 features are combined into one
vector and fed to a trained XGBoost classifier.
    """)

    st.divider()

    # ── Dataset Info ──────────────────────────────────────────────────────────
    st.markdown("### Dataset: Devign")
    st.markdown("""
- **27,318** C functions (FFmpeg + QEMU)
- Binary labels: Vulnerable / Safe
- NeurIPS 2019 benchmark
    """)

    st.divider()

    # ── Model Selection ───────────────────────────────────────────────────────
    st.markdown("### Model Selection")

    # st.selectbox() creates a dropdown menu.
    # The options list is the choices; the function returns the selected string.
    model_choice = st.selectbox(
        "Choose classifier:",
        ["XGBoost", "Random Forest"],
        help=(
            "XGBoost achieves F1=0.824 (recommended). "
            "Random Forest achieves F1=0.769."
        ),
    )

    st.divider()

    # ── Model Status ──────────────────────────────────────────────────────────
    st.markdown("### Model Status")

    # Check which files exist and show green/red indicators
    xgb_exists = os.path.exists(XGB_MODEL_PATH)
    rf_exists  = os.path.exists(RF_MODEL_PATH)

    # st.success / st.error / st.warning render coloured boxes
    if xgb_exists:
        st.success("XGBoost model: Loaded")
    else:
        st.warning("XGBoost model: Not found")
        st.caption(f"Expected at: models/xgboost.json")

    if rf_exists:
        st.success("Random Forest: Loaded")
    else:
        st.warning("Random Forest: Not found")
        st.caption(f"Expected at: models/random_forest.joblib")

    if not xgb_exists and not rf_exists:
        st.info(
            "No trained models found. Running in DEMO mode "
            "(heuristic-based prediction). Run Day 9 training script to generate models."
        )

    st.divider()

    # ── Performance Summary ───────────────────────────────────────────────────
    st.markdown("### Published Results (Devign)")
    st.markdown("""
| Model     | F1 Score |
|-----------|----------|
| XGBoost   | 0.8242   |
| Rand. Forest | 0.7692 |
| CodeBERT alone | 0.628 |
| Devign GNN | 0.561 |
    """)

    st.divider()

    # ── Author ────────────────────────────────────────────────────────────────
    st.markdown("### Project Info")
    st.caption("MCA Final Semester Project")
    st.caption("Multi-Modal Code Vulnerability Detection")
    st.caption("Using CodeBERT and Structural Code Analysis")


# =============================================================================
# SECTION 5: MAIN CONTENT AREA
# =============================================================================

# ── Main Title ────────────────────────────────────────────────────────────────
st.title("Multi-Modal Code Vulnerability Detector")
st.markdown(
    "Analyse C source code for security vulnerabilities using "
    "**AST features + Software Metrics + CodeBERT embeddings**."
)
st.divider()


# =============================================================================
# SECTION 6: CODE INPUT AREA
# =============================================================================
#
# We provide TWO ways for the user to input code:
#   Tab 1: Paste code directly into a text area
#   Tab 2: Upload a .c or .txt file
#
# st.tabs() creates a tabbed interface.
# It returns a list of tab container objects.
# "with tab1:" makes all content inside go into that tab.

tab_paste, tab_upload, tab_examples = st.tabs([
    "  Paste Code  ",
    "  Upload File  ",
    "  Load Example  ",
])

input_code = ""   # will hold the final code to analyse

# ── Tab 1: Paste Code ─────────────────────────────────────────────────────────
with tab_paste:
    st.markdown("**Paste your C function below:**")

    # st.text_area() creates a multi-line text input box.
    # - label:       The text shown above the box
    # - height:      Height in pixels
    # - placeholder: Ghost text shown when the box is empty
    # - key:         A unique identifier used by session_state
    pasted_code = st.text_area(
        label="C function code",
        height=280,
        placeholder=(
            "// Paste a C function here.\n"
            "// Example:\n"
            "void process(char *input) {\n"
            "    char buf[64];\n"
            "    strcpy(buf, input);  // potential buffer overflow\n"
            "}"
        ),
        label_visibility="collapsed",  # hide the label text (placeholder is enough)
        key="paste_area",
    )

    if pasted_code.strip():
        input_code = pasted_code


# ── Tab 2: Upload File ────────────────────────────────────────────────────────
with tab_upload:
    st.markdown("**Upload a C source file (.c, .h, .txt):**")

    # st.file_uploader() creates a drag-and-drop file upload widget.
    # type= restricts which file types are accepted.
    # The returned object is a file-like object (or None if no file uploaded).
    uploaded_file = st.file_uploader(
        label="Upload C file",
        type=["c", "h", "cpp", "txt"],
        label_visibility="collapsed",
        key="file_upload",
    )

    if uploaded_file is not None:
        # .read() reads all bytes from the uploaded file.
        # .decode("utf-8", errors="replace") converts bytes to a string.
        # errors="replace" replaces invalid bytes with ? instead of crashing.
        file_content = uploaded_file.read().decode("utf-8", errors="replace")
        input_code   = file_content

        # Show a preview so the user can confirm the right file was uploaded
        st.success(f"File uploaded: **{uploaded_file.name}** ({len(file_content)} characters)")
        with st.expander("Preview uploaded code"):
            # st.code() renders text with syntax highlighting.
            # language="c" applies C syntax highlighting.
            st.code(file_content[:2000], language="c")   # show first 2000 chars
            if len(file_content) > 2000:
                st.caption(f"... (showing first 2000 of {len(file_content)} characters)")


# ── Tab 3: Load Examples ──────────────────────────────────────────────────────
with tab_examples:
    st.markdown("**Choose a built-in example to test the detector:**")

    # Pre-defined example functions for demonstration
    # These are representative C patterns -- not from the actual Devign dataset
    EXAMPLES = {
        "Buffer Overflow (Vulnerable)": """\
/* Vulnerable: no bounds check on strcpy */
void copy_user_data(char *user_input) {
    char buffer[64];
    strcpy(buffer, user_input);   /* copies without checking length */
    process_data(buffer);
}""",
        "Bounds-Checked Copy (Safe)": """\
/* Safe: bounds-checked string copy */
void copy_user_data(char *user_input, size_t input_len) {
    char buffer[64];
    if (input_len >= sizeof(buffer)) {
        fprintf(stderr, "Input too large\\n");
        return;
    }
    strncpy(buffer, user_input, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\\0';
    process_data(buffer);
}""",
        "Integer Overflow Risk (Vulnerable)": """\
/* Vulnerable: integer overflow in size calculation */
void allocate_array(int n, int m) {
    int *arr = (int *)malloc(n * m * sizeof(int));  /* n*m can overflow */
    if (arr == NULL) return;
    for (int i = 0; i < n * m; i++) {
        arr[i] = 0;
    }
    free(arr);
}""",
        "Null Pointer Dereference (Vulnerable)": """\
/* Vulnerable: return value of malloc not checked */
char *create_buffer(size_t size) {
    char *buf = (char *)malloc(size);
    buf[0] = '\\0';    /* crash if malloc returns NULL */
    return buf;
}""",
        "Null-Safe Allocation (Safe)": """\
/* Safe: malloc return value checked */
char *create_buffer(size_t size) {
    if (size == 0) return NULL;
    char *buf = (char *)malloc(size);
    if (buf == NULL) {
        perror("malloc failed");
        return NULL;
    }
    buf[0] = '\\0';
    return buf;
}""",
        "Complex Function with Loops (Vulnerable)": """\
/* Vulnerable: loop without bounds, pointer arithmetic errors */
int process_packets(unsigned char *data, int len) {
    int i, count = 0;
    unsigned char *ptr = data;
    for (i = 0; i < len; i++) {
        if (*ptr == 0xFF) {
            int size = *(ptr + 1);   /* unchecked read */
            memcpy(ptr + 2, data + count, size);  /* no bounds check */
            count += size;
            ptr += size + 2;
        } else {
            ptr++;
        }
    }
    return count;
}""",
    }

    # st.radio() creates radio button options
    # The selected string is returned
    example_choice = st.radio(
        "Select example:",
        list(EXAMPLES.keys()),
        label_visibility="collapsed",
    )

    # Show the selected example
    selected_code = EXAMPLES[example_choice]
    st.code(selected_code, language="c")

    # Button to load this example into the analysis
    if st.button("Use This Example", type="secondary"):
        # st.session_state stores values that persist across reruns.
        # Setting a session_state key causes the next rerun to pick it up.
        st.session_state["example_loaded"] = selected_code
        input_code = selected_code
        st.success(f"Example loaded: **{example_choice}**")

# If an example was loaded from the button, use it
if st.session_state.get("example_loaded"):
    input_code = st.session_state["example_loaded"]


# =============================================================================
# SECTION 7: ANALYSIS TRIGGER
# =============================================================================

st.divider()

# Layout: show code preview on the left, button on the right
col_preview, col_btn = st.columns([4, 1])

with col_preview:
    if input_code.strip():
        # Show a one-line summary of what code is loaded
        lines = input_code.strip().split("\n")
        st.caption(
            f"Ready to analyse: {len(lines)} lines, "
            f"{len(input_code)} characters | Model: **{model_choice}**"
        )
    else:
        st.caption("No code loaded. Use one of the tabs above to provide a C function.")

with col_btn:
    # st.button() creates a clickable button.
    # type="primary" makes it the highlighted/main-action button (blue).
    # When clicked, the script reruns and st.button() returns True on that rerun.
    analyse_clicked = st.button(
        "Analyse Code",
        type="primary",
        disabled=(not input_code.strip()),   # greyed out if no code is loaded
        use_container_width=True,
    )

# Clear example after use so it doesn't persist unintentionally
if analyse_clicked and "example_loaded" in st.session_state:
    del st.session_state["example_loaded"]


# =============================================================================
# SECTION 8: PREDICTION AND RESULTS
# =============================================================================
#
# This entire block only runs if the user clicked "Analyse Code" AND
# there is code in input_code. Streamlit re-evaluates this condition
# on every rerun (i.e., every user interaction).

if analyse_clicked and input_code.strip():

    # ── Step A: Validate the input ────────────────────────────────────────────
    is_valid, validation_msg = validate_code(input_code)

    if not is_valid:
        # Show an error box and stop processing
        st.error(f"Invalid input: {validation_msg}")
        st.stop()   # st.stop() halts script execution here

    if validation_msg != "OK":
        # Show a non-blocking warning (code is still valid but user should know)
        st.warning(validation_msg)

    # ── Step B: Load models ───────────────────────────────────────────────────
    #
    # We call get_xgboost() and get_rf() here -- these are cached, so the actual
    # loading only happens the first time. Subsequent calls are instant.

    xgb_model = get_xgboost()
    rf_model  = get_rf()

    # Choose which model to use based on sidebar selection
    if model_choice == "XGBoost" and xgb_model is not None:
        active_model      = xgb_model
        active_model_name = "XGBoost"
    elif model_choice == "Random Forest" and rf_model is not None:
        active_model      = rf_model
        active_model_name = "Random Forest"
    elif xgb_model is not None:
        active_model      = xgb_model
        active_model_name = "XGBoost (fallback)"
    elif rf_model is not None:
        active_model      = rf_model
        active_model_name = "Random Forest (fallback)"
    else:
        active_model      = None   # demo mode
        active_model_name = None

    # ── Step C: Load CodeBERT (only needed if a real model is available) ───────
    tokenizer, codebert_model = None, None
    if active_model is not None:
        # st.spinner() shows a loading animation while the indented code runs.
        # This is important for CodeBERT which can take 2-10 seconds.
        with st.spinner("Loading CodeBERT embeddings..."):
            tokenizer, codebert_model = get_codebert()

    # ── Step D: Run prediction ────────────────────────────────────────────────
    with st.spinner(f"Analysing code with {active_model_name or 'Demo Heuristic'}..."):
        if active_model is not None:
            result = predict_with_model(
                input_code,
                active_model,
                active_model_name,
                tokenizer,
                codebert_model,
            )
        else:
            # No trained model available -- use heuristic demo predictor
            result = demo_predict(input_code)

    # ── Demo Mode Warning ─────────────────────────────────────────────────────
    if result.get("is_demo", False):
        st.warning(
            "**DEMO MODE:** No trained models were found. "
            "This prediction uses a simple heuristic based on pointer count, "
            "loop count, and nesting depth. It is for demonstration only. "
            "Run `src/model/train_classifier.py` to generate real models."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # RESULTS DISPLAY
    # ─────────────────────────────────────────────────────────────────────────

    st.divider()
    st.markdown("## Analysis Results")

    # ── Layout: left column (verdict + metrics) | right column (insights) ─────
    col_left, col_right = st.columns([5, 4], gap="large")

    with col_left:

        # ── VERDICT BOX ───────────────────────────────────────────────────────
        #
        # We use HTML to render a coloured box because Streamlit's built-in
        # widgets don't support large, coloured, styled text natively.

        verdict    = result["verdict"]          # "VULNERABLE" or "NOT VULNERABLE"
        risk_color = result["risk_color"]       # CSS hex colour
        risk_level = result["risk_level"]       # "HIGH RISK", "SAFE", etc.

        st.markdown(
            f"""
            <div class="verdict-box" style="background: {risk_color}22;
                 border-color: {risk_color};">
                <h1 style="color: {risk_color};">{verdict}</h1>
                <h3 style="color: {risk_color};">{risk_level}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── METRIC CARDS ──────────────────────────────────────────────────────
        #
        # st.columns() creates a row of evenly-spaced columns.
        # We create 3 columns to hold the three score cards.

        m1, m2, m3 = st.columns(3)

        with m1:
            # Vulnerability probability (0% = definitely safe, 100% = definitely vuln)
            vuln_pct = result["vuln_probability"]
            st.markdown(
                f"""<div class="metric-card">
                    <div class="value" style="color:{risk_color};">{vuln_pct:.1f}%</div>
                    <div class="label">Vuln Probability</div>
                </div>""",
                unsafe_allow_html=True,
            )

        with m2:
            # Safe probability
            safe_pct = result["safe_probability"]
            st.markdown(
                f"""<div class="metric-card">
                    <div class="value">{safe_pct:.1f}%</div>
                    <div class="label">Safe Probability</div>
                </div>""",
                unsafe_allow_html=True,
            )

        with m3:
            # Confidence in the prediction (how sure is the model?)
            conf_pct = result["confidence"]
            st.markdown(
                f"""<div class="metric-card">
                    <div class="value">{conf_pct:.1f}%</div>
                    <div class="label">Confidence</div>
                </div>""",
                unsafe_allow_html=True,
            )

        # ── CONFIDENCE PROGRESS BAR ───────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='section-header'>Vulnerability Probability</div>",
            unsafe_allow_html=True,
        )

        # st.progress() renders a horizontal progress bar.
        # value must be between 0.0 and 1.0
        st.progress(
            value=result["vuln_probability"] / 100.0,
            text=f"{result['vuln_probability']:.1f}% probability of vulnerability",
        )

        # ── MODEL INFO ────────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(f"Model used: **{result['model_used']}**")
        if not result.get("is_demo", False):
            shape = result.get("feature_vector_shape", (1, 792))
            st.caption(
                f"Feature vector: {shape[1]} dimensions "
                f"(11 AST + 13 Metrics + 768 CodeBERT)"
            )
            st.caption(f"Embedding source: {result.get('embedding_source','')}")


    # ── RIGHT COLUMN: RISK BREAKDOWN + INSIGHTS ───────────────────────────────
    with col_right:

        # ── RISK LEVEL EXPLANATION ────────────────────────────────────────────
        st.markdown(
            "<div class='section-header'>Risk Interpretation</div>",
            unsafe_allow_html=True,
        )

        # Risk level colour-coded explanation
        risk_tag = result["risk_tag"]
        if risk_tag == "safe":
            st.success(
                "**SAFE:** The model is highly confident this function "
                "does not contain a vulnerability. No immediate action required."
            )
        elif risk_tag == "low":
            st.success(
                "**LOW RISK:** Likely safe, but with some structural features "
                "that weakly correlate with vulnerabilities. Consider a quick review."
            )
        elif risk_tag == "medium":
            st.warning(
                "**MEDIUM RISK:** This function shows patterns associated with "
                "vulnerability. Manual code review is recommended, "
                "focusing on pointer operations and loop bounds."
            )
        elif risk_tag == "high":
            st.error(
                "**HIGH RISK:** The model strongly suspects a vulnerability. "
                "This function should be prioritised for security review. "
                "Common causes: unchecked pointer dereferences, unbounded loops."
            )
        else:   # critical
            st.error(
                "**CRITICAL:** The model is highly confident this function "
                "is vulnerable. Immediate review is required. "
                "Do NOT deploy this code without a security audit."
            )

        # ── STRUCTURAL INSIGHTS ───────────────────────────────────────────────
        st.markdown(
            "<div class='section-header'>Structural Insights</div>",
            unsafe_allow_html=True,
        )

        ast_feats    = result.get("ast_features", {})
        metric_feats = result.get("metric_features", {})
        insights     = describe_features(ast_feats, metric_feats)

        for insight_text, severity in insights:
            if severity == "warning":
                st.warning(insight_text)
            elif severity == "info":
                st.info(insight_text)
            else:
                st.success(insight_text)


    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE BREAKDOWN TABLES (collapsible)
    # ─────────────────────────────────────────────────────────────────────────

    st.divider()

    # st.expander() creates a collapsible section.
    # expanded=False means it starts collapsed.

    with st.expander("View Extracted Features", expanded=False):

        fa_col, fm_col = st.columns(2)

        # ── AST Features Table ────────────────────────────────────────────────
        with fa_col:
            st.markdown(
                "<div class='section-header'>AST Features (11)</div>",
                unsafe_allow_html=True,
            )

            # Build rows of HTML for each feature
            rows_html = ""
            for feat_name, feat_val in ast_feats.items():
                rows_html += (
                    f"<div class='feat-row'>"
                    f"<span class='feat-name'>{feat_name}</span>"
                    f"<span class='feat-value'>{feat_val}</span>"
                    f"</div>"
                )
            st.markdown(rows_html, unsafe_allow_html=True)

        # ── Software Metrics Table ────────────────────────────────────────────
        with fm_col:
            st.markdown(
                "<div class='section-header'>Software Metrics (13)</div>",
                unsafe_allow_html=True,
            )

            rows_html = ""
            for feat_name, feat_val in metric_feats.items():
                if isinstance(feat_val, float):
                    display_val = f"{feat_val:.2f}"
                else:
                    display_val = str(feat_val)
                rows_html += (
                    f"<div class='feat-row'>"
                    f"<span class='feat-name'>{feat_name}</span>"
                    f"<span class='feat-value'>{display_val}</span>"
                    f"</div>"
                )
            st.markdown(rows_html, unsafe_allow_html=True)

        # ── CodeBERT Embedding Info ───────────────────────────────────────────
        st.divider()
        n_dims = result.get("embedding_dims", 0)
        emb_src = result.get("embedding_source", "Unknown")
        if n_dims > 0:
            st.info(
                f"**CodeBERT Embeddings:** {n_dims}-dimensional [CLS] token vector "
                f"extracted from `{emb_src}`. "
                "Individual dimensions are not human-interpretable; they collectively "
                "encode the semantic meaning of the function."
            )
        else:
            st.warning(
                "CodeBERT embeddings were not used (demo mode or model not loaded). "
                "Prediction accuracy will be reduced."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYSED CODE VIEW
    # ─────────────────────────────────────────────────────────────────────────

    with st.expander("View Analysed Code", expanded=False):
        # st.code() renders with syntax highlighting
        st.code(input_code, language="c")


# =============================================================================
# SECTION 9: FOOTER -- HOW IT WORKS
# =============================================================================

st.divider()

with st.expander("How Does This Work?", expanded=False):
    st.markdown("""
### Detection Pipeline

When you click **Analyse Code**, the following steps happen:

**Step 1 — AST Parsing (Branch 1)**
```
C source code  -->  tree-sitter parser  -->  Abstract Syntax Tree
                                         -->  11 structural features
```
tree-sitter converts your code into a parse tree. We walk every node and
count: pointer operations, loops, if-statements, function calls, nesting depth, etc.

---

**Step 2 — Software Metrics (Branch 2)**
```
C source code  -->  regex + line counting  -->  13 quality metrics
```
We count lines of code, comment density, nesting depth, operator count, pointer
count, and average line length using text pattern matching.

---

**Step 3 — CodeBERT Embedding (Branch 3)**
```
C source code  -->  BPE Tokenizer  -->  [CLS] + tokens + [SEP]  -->  CodeBERT (12 Transformer layers)
                                                                  -->  768-dim [CLS] embedding
```
The function is converted to token IDs, fed to the `microsoft/codebert-base`
Transformer (125M parameters), and the special [CLS] token's output vector
captures the semantic meaning of the entire function.

---

**Step 4 — Feature Fusion**
```
[11 AST] + [13 Metrics] + [768 CodeBERT] = 792-dim feature vector
```
All three branches are concatenated into one vector per function.

---

**Step 5 — Classification**
```
792-dim vector  -->  XGBoost (100 trees, max_depth=6)
                -->  [prob_safe, prob_vulnerable]
                -->  Verdict + Risk Level
```
The XGBoost classifier (trained on 27,318 Devign functions) outputs the
probability of vulnerability. If > 0.5, the function is classified as vulnerable.

---

### Why Multi-Modal?

A key finding of this project: **CodeBERT alone cannot distinguish** a
vulnerable `strcpy()` from a safe `strncpy()` call. The cosine similarity
between their embeddings is **0.9996** -- essentially identical in embedding
space. The structural features (AST + metrics) provide the additional signal
that resolves this ambiguity.

This is why combining three modalities achieves **F1 = 0.824**, compared to
**F1 = 0.628** for single-modal CodeBERT.
    """)

with st.expander("Risk Level Definitions", expanded=False):
    st.markdown("""
| Risk Level | Vuln Probability | Meaning                                    |
|------------|------------------|--------------------------------------------|
| SAFE       | < 30%            | Very unlikely to be vulnerable             |
| LOW RISK   | 30% – 50%        | Some suspicious patterns; quick review recommended |
| MEDIUM RISK| 50% – 70%        | Notable vulnerability indicators; review required   |
| HIGH RISK  | 70% – 85%        | Strong vulnerability signals; priority review       |
| CRITICAL   | > 85%            | Very high confidence of vulnerability; do not ship  |

**Note on False Negatives:** The model achieves Recall = 83.3%, meaning it
misses approximately 1 in 6 real vulnerabilities. A "SAFE" result from this
tool does NOT guarantee the code is free of vulnerabilities. Always combine
automated detection with manual code review.

**Note on False Positives:** Precision = 81.5%, meaning about 1 in 5 flagged
functions is actually safe. Not every "VULNERABLE" result requires action --
manual review determines whether the flag is legitimate.
    """)


# =============================================================================
# SECTION 10: INITIAL STATE (before any analysis is run)
# =============================================================================
#
# The if-block in Section 8 only renders if the user clicked "Analyse".
# When the app first loads, nothing has been clicked yet.
# We show a placeholder message to guide the user.

if not analyse_clicked:
    st.markdown("""
<div style="text-align:center; padding: 40px 20px; color: #888;">
    <p style="font-size: 1.1rem;">
        Paste or upload a C function above, then click <strong>Analyse Code</strong>
        to run the vulnerability detector.
    </p>
    <p style="font-size: 0.9rem;">
        Or switch to the <strong>Load Example</strong> tab to try a pre-built example.
    </p>
</div>
""", unsafe_allow_html=True)
