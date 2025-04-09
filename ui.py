import streamlit as st
import google.generativeai as genai
import json


# --- Configuration ---
# IMPORTANT: Make sure you have enabled the Generative Language API
# in your Google Cloud Project for this key.
# Also, `gemini-pro-vision` might have different availability/quotas.
try:

    genai.configure(api_key="AIzaSyD5jMB6FmRXKmdk0nvSe7fxYqD1w-x3meo")

    # --- Use gemini-pro-vision for multimodal input ---
    model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")

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

output = {}
if uploaded_file is not None:
    # No need to extract text first

    # 2. Define the prompt for Gemini
    # --- THIS IS WHERE YOU CUSTOMIZE YOUR PROMPT ---
    # Make the prompt suitable for analyzing a full PDF document
    gemini_prompt = """
    You are an expert data extraction tool specialized in analyzing PDF documents.
    Carefully examine the content and structure of the following PDF file.
    Identify the Consolidated statement of profit and loss and balance sheet in the pdf and retrieve the data.
    Retrieve the terms:

    Current Year Total Revenue
    Previous Year Total Revenue
    

    Total Expense

    Depriciation And Amortization

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
    Previous Year Trade Payables
    
    Current Year Current Liabilities
    Current Year Non-Current Liabilities
    
    

    Number of total outstanding Shares (Year end)
    
    Minority shares
        
    Return the value in dataframe format as the response. The first column should be the names of the values, second column should be the actual values and the third column should contain how the values are calculated wether they are directly 
    Dont give me the code to do this only return the dataframe.
    """

    # -----------------------------------------------

    st.info("🚀 Sending PDF to Financial Extractor for processing...")

    # 3. Call Gemini API with the uploader object
    with st.spinner("Financial Extractor is analyzing the PDF... (this may take a moment)"):
        gemini_response_text = call_gemini_api_with_pdf(gemini_prompt, uploaded_file)

    if gemini_response_text:
        st.success("✨ Financial Extractor processing complete!")

        # 4. Clean and Parse JSON response
        output = gemini_response_text

        if output is not None: # Check if parsing was successful (even if result is {})
            st.subheader("Extracted Information:")
            if not output: # Handle empty JSON object explicitly
                 st.info("Financial Extractor returned an empty JSON object, possibly indicating no specific structured data was found or extracted.")
            else:
                st.write(output) # Display the dataframe


else:
    st.info("Please upload a PDF file to start the extraction process.")

