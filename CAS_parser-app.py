import streamlit as st
import pikepdf
import pdfplumber
import pandas as pd
import numpy as np
import re
from collections import namedtuple
import time

# Unlock a password-protected PDF
def unlock_pdf(input_pdf, output_pdf, password):
    try:
        # Open the encrypted PDF with the provided password
        with pikepdf.open(input_pdf, password=password) as pdf:
            # Save the unlocked PDF to a new file
            pdf.save(output_pdf)
            return output_pdf
    except pikepdf.PasswordError:
        return None  # Return None if password is incorrect

# Extract portfolio summary and transactions from the unlocked PDF
def extract_data_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # Process portfolio summary
    portfolio_summary = []
    summary = re.compile(r'^(?!RMF).*(Mutual Fund|MF|MUTUAL FUND)(?!$) .*')
    for line in text.split('\n'):
        if summary.match(line):
            fund_house = ' '.join(line.split()[:-2])
            cost_value = line.split()[-2]
            market_value = line.split()[-1]
            portfolio_summary.append([fund_house, cost_value, market_value])

    # Convert portfolio summary to dataframe
    df_portfolio = pd.DataFrame(portfolio_summary, columns=['Fund House', 'Cost Value', 'Market Value'])
    df_portfolio["Market Value"] = [float(str(i).replace(",", "")) for i in df_portfolio["Market Value"]]
    df_portfolio["Cost Value"] = [float(str(i).replace(",", "")) for i in df_portfolio["Cost Value"]]
    market_value = np.array(df_portfolio['Market Value'])
    cost_value = np.array(df_portfolio['Cost Value'])
    df_portfolio['Absolute Returns (%)'] = (market_value / cost_value - 1) * 100

    # Add total row
    total_market_value = np.array(df_portfolio['Market Value']).sum()
    total_cost_value = np.array(df_portfolio['Cost Value']).sum()
    total_absolute_returns = (total_market_value / total_cost_value - 1) * 100
    df_portfolio.loc['Total'] = ['Total', total_cost_value, total_market_value, total_absolute_returns]

    # Extract transactions
    transactions_re = re.compile(
        r'(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+'
        r'(?P<description>.*?(Purchase|Investment|Redemption|Allotment|Switch In|Switch Out|Dividend Reinvestment|Dividend Payout).*)\s+'
        r'(?P<amount>\(?[\d,]*\.?\d*\)?)\s+'
        r'(?P<units>\(?[\d,]*\.?\d*\)?)\s+'
        r'(?P<nav>[\d,]*\.?\d*)\s+'
        r'(?P<unit_balance>\(?[\d,]*\.?\d*)'
    )
    transaction_list = []
    new_AMC = re.compile(r'.+\s(Mutual Fund|MF|MUTUAL FUND)$')
    for line in text.split('\n'):
        if new_AMC.match(line):
            AMC = line
        match = transactions_re.search(line)
        if match:
            transaction_date = match.group('date')
            transaction_description = match.group('description')
            transaction_amount = match.group('amount')
            transaction_units = match.group('units')
            transaction_nav = match.group('nav')
            transaction_unit_balance = match.group('unit_balance')
            transaction_list.append([AMC, transaction_date, transaction_description, transaction_amount, transaction_units, transaction_nav, transaction_unit_balance])

    # Convert transactions to dataframe
    df_transactions = pd.DataFrame(transaction_list, columns=['AMC', 'Date', 'Description', 'Amount', 'Units', 'NAV', 'Unit Balance'])

    return df_portfolio, df_transactions

# Streamlit UI
st.title("MF CAS Analytics")
st.caption("This app allows you to upload your Consolidated Account Statement (CAS) PDF, unlock it using the provided password, and analyze your mutual fund investments. You can view a summary of your portfolio, detailed transaction history, and insightful visualizations of your investments.")
# st.divider()

with st.expander("Upload your CAS PDF", expanded=True):
    # Upload PDF file
    uploaded_file = st.file_uploader("", type=["pdf"])

    # Password input
    password = st.text_input("Enter PDF password", type="password")

# Description of the app
if uploaded_file and password:
    # Save the uploaded file temporarily
    with open("uploaded_file.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Unlock the PDF using the provided password
    unlocked_pdf = unlock_pdf("uploaded_file.pdf", "unlocked.pdf", password)

    if unlocked_pdf:
        st.divider()
        # Extract data from unlocked PDF
        df_portfolio, df_transactions = extract_data_from_pdf(unlocked_pdf)

        # Display portfolio summary

        # Plot total row as pie chart using Plotly Express
        import plotly.express as px

        total_row = df_portfolio.loc['Total']
        labels = ['Investments', 'Returns']
        sizes = [total_row['Cost Value'], total_row['Market Value'] - total_row['Cost Value']]
        fig = px.pie(values=sizes, names=labels, title='Portfolio Summary')

        # Plot investments of various fund houses as pie chart
        fig_allocation = px.pie(df_portfolio.drop('Total'), values='Cost Value', names='Fund House', title='AMC Exposure')

        tab1, tab2, tab3 = st.tabs(["Portfolio Summary", "Transactions", "Insights"])
        
        with tab1:
            st.subheader("Portfolio Summary")
            st.dataframe(df_portfolio, hide_index=True, height=35 * len(df_portfolio) + 38,
            use_container_width=True)

        with tab2:
            # Display transactions
            # st.subheader("Transaction History")
            # Split transactions into purchases and redemptions
            df_purchases = df_transactions[df_transactions['Description'].str.contains('Purchase|Investment|Allotment|Switch In|Dividend Reinvestment')]
            df_redemptions = df_transactions[df_transactions['Description'].str.contains('Redemption|Switch Out|Dividend Payout')]

            # Display purchases
            st.subheader("Purchases")
            df_purchases = df_purchases.reset_index(drop=True)
            df_purchases.index = df_purchases.index + 1
            st.dataframe(df_purchases, use_container_width=True)

            # Group purchases by date and plot a bar chart to display total amount of purchases in that month
            
            # fig_purchases = px.bar(monthly_purchases, x='Month', y='Amount', title='Monthly Purchases')

            # Display redemptions
            st.subheader("Redemptions")
            df_redemptions = df_redemptions.reset_index(drop=True)
            df_redemptions.index = df_redemptions.index + 1
            st.dataframe(df_redemptions, use_container_width=True)

        with tab3: 
            # st.plotly_chart(fig_purchases)
            st.plotly_chart(fig)
            st.plotly_chart(fig_allocation)

    else:
        st.error("Incorrect password or unable to decrypt PDF.")
else:
    st.info("Please upload your CAS PDF and enter the password to unlock it.")

st.divider()
st.caption("Created with :heart: for Investors by [Kali Wealth](https://kaliwealth.in)") 
