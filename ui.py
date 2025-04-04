import streamlit as st
import google.generativeai as genai
# import fitz # No longer needed for direct PDF processing by Gemini
import json
# import io # io is implicitly used by getvalue() but explicit import isn't strictly needed here

# --- Configuration ---
# IMPORTANT: Make sure you have enabled the Generative Language API
# in your Google Cloud Project for this key.
# Also, `gemini-pro-vision` might have different availability/quotas.
try:

    genai.configure(api_key="AIzaSyC5ZtIPbveTdZw4sLWJ-mTR7tb4ZNj4ZQk")

    # --- Use gemini-pro-vision for multimodal input ---
    model = genai.GenerativeModel('gemini-2.0-flash')

except KeyError:
    st.error("API Key not found. Please add google_generativeai.api_key to your Streamlit secrets (secrets.toml).")
    st.stop()
except Exception as e:
    st.error(f"Error configuring Gemini: {e}")
    st.stop()

# --- Helper Functions ---

# We don't need extract_text_from_pdf anymore

def call_gemini_api_with_pdf(prompt, pdf_file_uploader):
    """Sends the prompt and PDF file bytes to Gemini Vision and gets the response."""
    try:
        # Read the bytes from the uploaded file
        pdf_bytes = pdf_file_uploader.getvalue()

        # Prepare the file part for the API call
        # Gemini Vision API expects a list containing text and inline data parts
        pdf_part = {
            "mime_type": "application/pdf", # Standard MIME type for PDF
            "data": pdf_bytes
        }

        # Generate content using the prompt and the PDF data
        # The input must be a list
        response = model.generate_content([prompt, pdf_part])

        # Handle potential safety flags or empty responses
        if not response.parts:
             if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 st.warning(f"Content blocked by Financial Extractor's safety filters: {response.prompt_feedback.block_reason_message}")
                 return None
             else:
                 st.warning("Financial Extractor returned an empty response.")
                 return None

        return response.text

    except Exception as e:
        # Specific error handling for potential API issues
        if "400" in str(e) and "User location is not supported" in str(e):
             st.error("Error calling Financial Extractor: The API key is valid, but your region might not be supported for this model yet. Check Google AI documentation for supported regions.")
        elif "API key not valid" in str(e):
             st.error("Error calling Financial Extractor: Invalid API Key. Please check your key in Streamlit secrets.")
        else:
            st.error(f"Error calling Financial Extractor: {e}")
        return None

def clean_and_parse_json(gemini_response):
    """Attempts to clean Gemini's response and parse it as JSON."""
    if not gemini_response:
        return None

    # Sometimes Gemini wraps the JSON in markdown ```json ... ```
    cleaned_response = gemini_response.strip()
    if cleaned_response.startswith("```json"):
        cleaned_response = cleaned_response[len("```json"):].strip()
    elif cleaned_response.startswith("```"): # Handle ``` without 'json'
        cleaned_response = cleaned_response[len("```"):].strip()

    if cleaned_response.endswith("```"):
        cleaned_response = cleaned_response[:-len("```")].strip()

    cleaned_response = cleaned_response.strip() # Remove leading/trailing whitespace

    try:
        # Try parsing the cleaned response
        json_data = json.loads(cleaned_response)
        return json_data
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse Financial Extractor's response as JSON: {e}")
        st.text_area("Raw Financial Extractor Response (for debugging)", gemini_response, height=150)
        return None
    except Exception as e: # Catch other potential errors during cleaning/parsing
        st.error(f"An unexpected error occurred while processing Gemini's response: {e}")
        st.text_area("Raw Financial Extractor Response (for debugging)", gemini_response, height=150)
        return None

# --- Streamlit App UI ---
st.set_page_config(page_title="PDF Extractor with Financial Extractor", layout="wide")
st.title("📄 PDF Information Extractor using Financial Extractor")
st.markdown("Upload a PDF file, provide a prompt, and Financial Extractor will analyze the file directly to extract information as JSON.")

# File Uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    # No need to extract text first

    # 2. Define the prompt for Gemini
    # --- THIS IS WHERE YOU CUSTOMIZE YOUR PROMPT ---
    # Make the prompt suitable for analyzing a full PDF document
    gemini_prompt = """
    You are an expert data extraction tool specialized in analyzing PDF documents.
    Carefully examine the content and structure of the following PDF file.
    Identify the Consolidated financial statements in the pdf and retrieve the data.
    Retrieve the terms Current Year Total Revenue
Previous Year Total Revenue
Revenue % Years 5 Ago
Cost of Goods Sold
Total Expense
EBITDA
Depriciation And Amortization
EBIT (Operating Profit)
Interest Expense (Finance Cost)
Net Profit
Current Year EPS
Previous Year EPS

Total Assets Current Year
Total Assets Previous Year
Average Total Assets
Previous Year Inventory 
Current Year Inventory
Average Inventory
Previous Year Receivables
Current Year Receivables
Previous Year Trade Payables
Current Year Trade Payables
Average Receivables
Cash & Cash Equivalent

Total Liabilities Current Year
Total Liabilities Previous Year
Total Shareholder's Equity
Total Debt
Previous Year Trade Payables

Current Year Current Liabilities
Current Year Non-Current Liabilities
Enterprise Value

Market Price per Share (year end)
Current Market Price
Market capitalisation (current)
Book Value per share
Number of total outstanding Shares (Year end)
Number of total outstanding Shares (Current)
Minority shares

Days Receivable
Days Payable
Days Inventory

If a particular term is not found set its value to NaN
    Structure your findings strictly as a JSON object. Use clear and descriptive keys.
    For example, if it's an invoice:
    {
      "document_type": "Invoice",
      "invoice_id": "INV-1234",
      "issue_date": "2024-01-15",
      "due_date": "2024-02-14",
      "issuer_name": "Supplier Ltd.",
      "issuer_address": "123 Supply St, Goods City, GC 54321",
      "customer_name": "Acme Corp",
      "customer_address": "456 Buyer Ave, Client Town, CT 12345",
      "line_items": [
        {"description": "Widget A", "quantity": 2, "unit_price": 50.00, "total": 100.00},
        {"description": "Service B", "quantity": 1, "unit_price": 50.75, "total": 50.75}
      ],
      "subtotal": 150.75,
      "tax_amount": 10.55,
      "total_amount": 161.30
    }
    Only return the JSON object, nothing else before or after it (no introductory text, no explanations, no markdown formatting like ```json).
    If the document doesn't contain easily extractable structured data, describe the document type and key topics found in the JSON object (e.g., {"document_type": "Research Paper", "title": "...", "authors": ["..."], "abstract_summary": "..."}).
    If no relevant information can be reliably extracted, return an empty JSON object {}.
    """
    # -----------------------------------------------

    st.info("🚀 Sending PDF to Financial Extractor for processing...")

    # 3. Call Gemini API with the uploader object
    with st.spinner("Financial Extractor is analyzing the PDF... (this may take a moment)"):
        gemini_response_text = call_gemini_api_with_pdf(gemini_prompt, uploaded_file)

    if gemini_response_text:
        st.success("✨ Financial Extractor processing complete!")

        # 4. Clean and Parse JSON response
        json_output = clean_and_parse_json(gemini_response_text)

        if json_output is not None: # Check if parsing was successful (even if result is {})
            st.subheader("Extracted Information (JSON):")
            if not json_output: # Handle empty JSON object explicitly
                 st.info("Financial Extractor returned an empty JSON object, possibly indicating no specific structured data was found or extracted.")
            else:
                st.json(json_output) # Display the parsed JSON
        # else: Error message is handled within clean_and_parse_json

    # else: Error messages are handled within call_gemini_api_with_pdf

else:
    st.info("Please upload a PDF file to start the extraction process.")
