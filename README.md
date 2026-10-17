# AI-Powered Product Testing Report Analyzer

## Project Overview

This project is developed for the MSc Emerging Topics in Information Technology (IT6070) Assignment II.

The application assists Product Development Engineers in evaluating LED product testing reports by automatically validating measurements against predefined specifications and generating AI-assisted technical summaries.

## Technologies Used

- Python
- Pandas
- Google Gemini API
- CSV data processing

## Features

**Feature 1 – Automated Test Validation**

Reads LED testing data from CSV files and compares five parameters against predefined specification limits:

- Input Power (W)
- Power Factor (PF)
- Luminous Efficacy (lm/W)
- Correlated Color Temperature (CCT)
- Colour Rendering Index (CRI)

Displays PASS/FAIL results and identifies non-compliant parameters.

**Feature 2 – AI-Assisted Technical Reporting**

Uses Google Gemini AI to generate failure summaries, possible technical causes and suggested corrective actions.

Generated technical summaries are saved to `report.txt`.

## Installation

1. Install Python.
2. Download or clone this repository.
3. Open a terminal in the project folder.
4. Install dependencies:

   `python -m pip install -r requirements.txt`

5. Set the `GEMINI_API_KEY` environment variable using your own Gemini API key.

## How to Run

Run the application:

`python validate.py`

The script reads the CSV filename currently configured in `validate.py`, validates the measurements and attempts to generate an AI summary for any detected failures.

To test another CSV dataset, update the CSV filename in the script before running it.

## Test Cases

| Test | Description | Observed result |
|---|---|---|
| TC01 | All compliant measurements | No failures identified |
| TC02 | Non-compliant measurements | Four failures detected; AI report generated |
| TC03 | Invalid CSV with missing PF column | Initially caused KeyError; error handling improvement identified |

## Limitations

- AI-generated recommendations require engineering verification.
- Input validation requires improvement.
- AI generation depends on API configuration and availability.

## Author

Subashi Withanage  
MS25907520  
MSc in Information Technology – SLIIT