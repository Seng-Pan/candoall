import io
import logging
import re

import cv2
import numpy as np
import pandas as pd
import pytesseract
import streamlit as st
from PIL import Image

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Regular expression patterns for extracting fields
date_pattern = re.compile(
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(\d{1,2} \w+ \d{4})|(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
)
number_pattern = re.compile(
    r"(Transaction(?:\sID|\.? No\.?)|Reference ID)\s?:?\s?([\w\d]+)"
)
amount_pattern = re.compile(r"[—-]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?(MMK|Ks|Kyat)?")
send_from_pattern = re.compile(r"(From|Sender Name|Send From)\s?:?\s?([A-Za-z\s]+)")
send_to_pattern = re.compile(r"(To|Receiver Name|Send To)\s?:?\s?([A-Za-z0-9\s]+)")
notes_pattern = re.compile(r"(Notes|Purpose)\s?:?\s?(.+)")


def extract_text_from_image(image):
    """
    Extracts text from an image using Tesseract OCR.

    :param image: Image file
    :return: Extracted text as a string, or None if extraction fails
    """
    try:
        # Convert the image to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Use Tesseract to do OCR on the image
        text = pytesseract.image_to_string(Image.fromarray(gray))

        return text
    except Exception as e:
        logging.error(f"Error processing image: {str(e)}")
        return None


def extract_transaction_details(text):
    """
    Extract key fields (transaction date, number, amount, sender, receiver, notes) from the given text.

    :param text: Text extracted from an image
    :return: Dictionary of extracted transaction details
    """
    details = {
        "transaction_date": None,
        "transaction_number": None,
        "amount": None,
        "send_from": None,
        "send_to": None,
        "notes": None,
    }

    # Find and store each field using regex
    date_match = date_pattern.search(text)
    if date_match:
        details["transaction_date"] = date_match.group(0)

    number_match = number_pattern.search(text)
    if number_match:
        details["transaction_number"] = number_match.group(2)

    amount_match = amount_pattern.search(text)
    if amount_match:
        details["amount"] = amount_match.group(0).replace("—", "-").strip()

    send_from_match = send_from_pattern.search(text)
    if send_from_match:
        details["send_from"] = send_from_match.group(2).strip()

    send_to_match = send_to_pattern.search(text)
    if send_to_match:
        details["send_to"] = send_to_match.group(2).strip()

    notes_match = notes_pattern.search(text)
    if notes_match:
        details["notes"] = notes_match.group(2).strip()

    return details


def main():
    st.title("Transaction Details Extractor")

    # Initialize session state for transaction details
    if "all_transaction_details" not in st.session_state:
        st.session_state.all_transaction_details = []

    uploaded_files = st.file_uploader(
        "Upload image files", accept_multiple_files=True, type=["png", "jpg", "jpeg"]
    )

    # Track processed files to avoid duplicates
    processed_files = {
        detail["image_file"] for detail in st.session_state.all_transaction_details
    }

    for uploaded_file in uploaded_files:
        if uploaded_file.name not in processed_files:
            try:
                # Read the image file
                image = Image.open(uploaded_file)
                image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

                # Extract text from the image
                extracted_text = extract_text_from_image(image_cv)

                if extracted_text:
                    # Extract transaction details using regex
                    transaction_details = extract_transaction_details(extracted_text)
                    transaction_details["image_file"] = uploaded_file.name

                    # Append the extracted details to the session state list
                    st.session_state.all_transaction_details.append(transaction_details)
                else:
                    st.warning(f"Failed to extract text from {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {e}")

    # Display all transaction details in a DataFrame with custom column names
    if st.session_state.all_transaction_details:
        df = pd.DataFrame(st.session_state.all_transaction_details)

        # Reorder columns to have 'Amount' at the end
        df = df[
            [
                "transaction_date",
                "transaction_number",
                "send_from",
                "send_to",
                "notes",
                "image_file",
                "amount",
            ]
        ]

        # Rename columns for display
        df.columns = [
            "Transaction Date",
            "Transaction Number",
            "Sender",
            "Receiver",
            "Notes",
            "Image File",
            "Amount",
        ]

        # Convert 'Amount' to numeric, handling any non-numeric values
        df["Amount"] = pd.to_numeric(
            df["Amount"].replace("[^\d.]", "", regex=True), errors="coerce"
        )

        # Configure the DataFrame display with column_config
        st.dataframe(
            df,
            column_config={
                "Transaction Date": "Date",
                "Transaction Number": "Number",
                "Sender": "From",
                "Receiver": "To",
                "Notes": "Notes",
                "Image File": "File",
                "Amount": st.column_config.NumberColumn(
                    "Amount",
                    help="Transaction amount in currency",
                    format="%.2f",  # Format to two decimal places
                    min_value=0.0,  # Minimum value constraint
                ),
            },
            hide_index=True,
        )

        # Calculate and display the total amount
        total_amount = df["Amount"].sum()
        st.write(f"**Total Amount:** {total_amount}")

        # Export DataFrame to Excel
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")

        # Provide a download button for the Excel file
        st.download_button(
            label="Download Excel",
            data=excel_buffer,
            file_name="transaction_details.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.success("All transaction details have been extracted successfully.")


if __name__ == "__main__":
    main()
