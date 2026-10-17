

import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

SPECS = {
    "Input Power (W)": (8.1, 9.9),
    "PF": (0.90, 1.00),
    "Efficacy (lm/W)": (100, 999),
    "CCT (K)": (6000, 7000),
    "CRI": (80, 100),
}


def read_and_validate_csv(csv_path):
    """Check CSV structure and numeric measurements before evaluating specs."""
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise ValueError(f"CSV file not found: {csv_path}") from None
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError) as exc:
        raise ValueError(f"Unable to read CSV file: {exc}") from None

    required = ["Sample", *SPECS.keys()]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if df.empty:
        raise ValueError("CSV file contains no sample rows.")
    if df["Sample"].isna().any() or df["Sample"].astype(str).str.strip().eq("").any():
        raise ValueError("The Sample column contains empty sample identifiers.")

    for column in SPECS:
        converted = pd.to_numeric(df[column], errors="coerce")
        invalid = converted.isna() | ~converted.map(lambda value: pd.notna(value) and abs(value) != float("inf"))
        if invalid.any():
            rows = ", ".join(str(i + 2) for i in df.index[invalid])
            raise ValueError(f"Invalid or missing numeric value in '{column}' at CSV row(s): {rows}")
        df[column] = converted
    return df


def calculate_results(df):
    rows = []
    for _, sample in df.iterrows():
        for parameter, (minimum, maximum) in SPECS.items():
            measured = float(sample[parameter])
            status = "PASS" if minimum <= measured <= maximum else "FAIL"
            if measured < minimum:
                deviation = measured - minimum
                issue = f"Below minimum by {abs(deviation):g}"
            elif measured > maximum:
                deviation = measured - maximum
                issue = f"Above maximum by {deviation:g}"
            else:
                deviation = 0.0
                issue = "Within specification"
            rows.append({
                "Sample": str(sample["Sample"]),
                "Parameter": parameter,
                "Measured": measured,
                "Minimum": minimum,
                "Maximum": maximum,
                "Specification": f"{minimum:g} - {maximum:g}",
                "Status": status,
                "Deviation": deviation,
                "Issue": issue,
            })
    return pd.DataFrame(rows)


def make_graph(results, output_path):
    failures = (results.loc[results["Status"] == "FAIL", "Parameter"]
                .value_counts().reindex(SPECS.keys(), fill_value=0))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(failures.index, failures.values,
                  color=["#d64d4d" if n else "#36966b" for n in failures.values])
    ax.set_title("LED Testing - Failures by Parameter")
    ax.set_ylabel("Number of failed checks")
    ax.set_ylim(0, max(1.5, failures.max() + 0.8))
    ax.set_yticks(range(0, max(2, int(failures.max()) + 2)))
    ax.bar_label(bars, padding=3)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def create_local_summary(results):
    failed = results[results["Status"] == "FAIL"]
    if failed.empty:
        return "All measured LED parameters are within the configured specification limits."
    lines = ["Non-compliant measurements (verify with an engineer):"]
    for _, row in failed.iterrows():
        lines.append(f"- {row['Sample']}: {row['Parameter']} = {row['Measured']:g}; "
                     f"required {row['Specification']}; {row['Issue']}.")
    lines.append("Possible causes and corrective actions require engineering investigation.")
    return "\n".join(lines)


def generate_ai_analysis(results):
    failed = results[results["Status"] == "FAIL"]
    if failed.empty:
        return "No failed checks were detected. AI analysis was not required.", "NOT_NEEDED"

    fallback = create_local_summary(results)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return ("Gemini analysis unavailable: GEMINI_API_KEY is not configured.\n\n" + fallback,
                "FALLBACK")

    prompt = (
        "You are assisting a product development engineer reviewing LED test data. "
        "The numeric compliance decisions below were calculated by Python and must not "
        "be changed. Explain each failure, suggest plausible technical causes, practical "
        "verification steps and possible corrective actions. Clearly distinguish hypotheses "
        "from confirmed findings. Do not invent test results. Keep the response concise "
        "and include a note that an engineer must verify recommendations.\n\n"
        + failed[["Sample", "Parameter", "Measured", "Specification", "Issue"]]
          .to_string(index=False)
    )
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        output = (response.text or "").strip()
        if not output:
            raise RuntimeError("Gemini returned an empty response")
        return output, "SUCCESS"
    except Exception as exc:
        # Do not print the exception: some SDK errors can include request details.
        return (f"Gemini analysis unavailable ({type(exc).__name__}). "
                "Local validation remains available.\n\n" + fallback, "FALLBACK")


def create_pdf(results, analysis, graph_path, pdf_path, source_name, ai_status):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf_path), pagesize=(11.7 * inch, 8.3 * inch),
                            rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32)
    total = len(results)
    failed = int((results["Status"] == "FAIL").sum())
    story = [
        Paragraph("LED Product Testing Analysis Report", styles["Title"]),
        Paragraph(f"Input file: {escape(source_name)}", styles["Normal"]),
        Paragraph(f"Checks: {total} | PASS: {total - failed} | FAIL: {failed} | "
                  f"AI status: {escape(ai_status)}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Detailed Test Results", styles["Heading2"]),
    ]
    headers = ["Sample", "Parameter", "Measured", "Specification", "Status", "Issue"]
    data = [[Paragraph(escape(h), styles["BodyText"]) for h in headers]]
    for _, r in results.iterrows():
        data.append([
            Paragraph(escape(str(r["Sample"])), styles["BodyText"]),
            Paragraph(escape(str(r["Parameter"])), styles["BodyText"]),
            Paragraph(f"{r['Measured']:g}", styles["BodyText"]),
            Paragraph(escape(str(r["Specification"])), styles["BodyText"]),
            Paragraph(escape(str(r["Status"])), styles["BodyText"]),
            Paragraph(escape(str(r["Issue"])), styles["BodyText"]),
        ])
    table = Table(data, colWidths=[55, 115, 65, 85, 55, 180], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce6f2")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    for row_index, r in enumerate(results.itertuples(index=False), start=1):
        if r.Status == "FAIL":
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#fff0f0"))
            ]))
    story += [table, Spacer(1, 16), Paragraph("Failure Analysis Graph", styles["Heading2"]),
              Image(str(graph_path), width=650, height=325), Spacer(1, 14),
              Paragraph("AI-Assisted Technical Analysis", styles["Heading2"])]
    for line in analysis.splitlines():
        if line.strip():
            story.append(Paragraph(escape(line), styles["BodyText"]))
            story.append(Spacer(1, 5))
    story += [Spacer(1, 8), Paragraph(
        "Note: Specification decisions are computed locally. AI suggestions are not "
        "verified diagnoses and require engineering review.", styles["Italic"])]
    doc.build(story)


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("led_samples.csv")
    try:
        df = read_and_validate_csv(csv_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    results = calculate_results(df)
    print("\n=== LED TEST RESULTS ===")
    print(results[["Sample", "Parameter", "Measured", "Specification", "Status", "Issue"]]
          .to_string(index=False))
    pass_count = int((results["Status"] == "PASS").sum())
    fail_count = len(results) - pass_count
    print(f"\nSUMMARY: {len(results)} checks | {pass_count} PASS | {fail_count} FAIL")

    results.to_csv("detailed_results.csv", index=False)
    make_graph(results, "failure_analysis.png")
    print("Saved detailed_results.csv and failure_analysis.png")

    analysis, ai_status = generate_ai_analysis(results)
    Path("report.txt").write_text(analysis, encoding="utf-8")
    print(f"\n=== TECHNICAL ANALYSIS ({ai_status}) ===\n{analysis}")
    print("Saved report.txt")

    create_pdf(results, analysis, "failure_analysis.png", "LED_Test_Analysis_Report.pdf",
               csv_path.name, ai_status)
    print("Saved LED_Test_Analysis_Report.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
