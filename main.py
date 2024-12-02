import streamlit as st
import psycopg2

# Retrieve the database credentials securely from Streamlit secrets
DBNAME = st.secrets["postgres"]["DBNAME"]
DBUSER = st.secrets["postgres"]["DBUSER"]
DBPASSWORD = st.secrets["postgres"]["DBPASSWORD"]
DBHOST = st.secrets["postgres"]["DBHOST"]
DBPORT = st.secrets["postgres"]["DBPORT"]

# Establish the connection to PostgreSQL
conn = psycopg2.connect(
    dbname=DBNAME,
    user=DBUSER,
    password=DBPASSWORD,
    host=DBHOST,
    port=DBPORT
)

# Test the connection
st.write("Connected to PostgreSQL database successfully!")

# Remember to close the connection after use
conn.close()
