import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()



class PatientHealthMonitor:
    def __init__(self, dbname, user, password, host):
        """Initialize database connection parameters"""
        self.db_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host
        }
        self.conn = None
        self.cursor = None

    def connect_to_database(self):
        """Establish a connection to the PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(**self.db_params)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            st.error(f"Database Connection Error: {e}")
            return False

    def fetch_patient_data_by_date(self, selected_date):
        """
        Fetch patient health data for a specific date
        """
        query = """
        WITH LatestReadings AS (
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.gender,
                EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.date_of_birth)) as age,
                p.contact_info,
                bp.record_date,
                bp.systolic,
                bp.diastolic,
                hr.heart_rate,
                hr.record_timestamp AS hr_timestamp,
                o2.oxygen_level,
                o2.record_timestamp AS o2_timestamp,
                d.glucose_level,
                d.record_date AS diabetes_record_date,
                -- Remove a1c_level if it doesn't exist
                ROW_NUMBER() OVER (
                    PARTITION BY p.patient_id 
                    ORDER BY bp.record_date DESC, 
                             hr.record_timestamp DESC,
                             o2.record_timestamp DESC,
                             d.record_date DESC
                ) as rn
            FROM 
                Patients p
            LEFT JOIN 
                BloodPressure bp ON p.patient_id = bp.patient_id
                AND bp.record_date = %s
            LEFT JOIN 
                HeartRate hr ON p.patient_id = hr.patient_id
                AND DATE(hr.record_timestamp) = %s
            LEFT JOIN 
                Oxygen o2 ON p.patient_id = o2.patient_id
                AND DATE(o2.record_timestamp) = %s
            LEFT JOIN 
                Diabetes d ON p.patient_id = d.patient_id
                AND d.record_date = %s
        )
        SELECT * FROM LatestReadings WHERE rn = 1;
        """
        try:
            return pd.read_sql_query(query, self.conn, params=(selected_date, selected_date, selected_date, selected_date))
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()

    def assess_health_risks(self, df):
        """Assess health risks based on vital signs"""
        def assess_bp_risk(row):
            try:
                if pd.isna(row['systolic']) or pd.isna(row['diastolic']):
                    return 'No Data'
                if row['systolic'] >= 180 or row['diastolic'] >= 120:
                    return 'Crisis'
                if row['systolic'] >= 140 or row['diastolic'] >= 90:
                    return 'High Risk'
                if row['systolic'] >= 120 or row['diastolic'] >= 80:
                    return 'Elevated'
                return 'Normal'
            except:
                return 'Error'

        def assess_hr_risk(heart_rate):
            if pd.isna(heart_rate):
                return 'No Data'
            if heart_rate > 120:
                return 'High Risk'
            if heart_rate < 60:
                return 'Low Risk'
            return 'Normal'

        def assess_o2_risk(oxygen_level):
            if pd.isna(oxygen_level):
                return 'No Data'
            if oxygen_level < 90:
                return 'Critical'
            if oxygen_level < 95:
                return 'At Risk'
            return 'Normal'

        def assess_diabetes_risk(row):
            # Check if a1c_level column exists
            has_a1c = 'a1c_level' in row.index

            # No data scenario
            if pd.isna(row['glucose_level']) and (has_a1c and pd.isna(row['a1c_level'])):
                return 'No Data'
            
            # A1C risk assessment if column exists
            a1c_risk = 'Normal'
            if has_a1c and not pd.isna(row['a1c_level']):
                if row['a1c_level'] > 8:
                    a1c_risk = 'High Risk'
                elif row['a1c_level'] > 7:
                    a1c_risk = 'At Risk'
            
            # Glucose level risk assessment
            glucose_risk = 'Normal'
            if not pd.isna(row['glucose_level']):
                if row['glucose_level'] > 200:
                    glucose_risk = 'High Risk'
                elif row['glucose_level'] > 140:
                    glucose_risk = 'At Risk'
            
            # Combine risks
            if a1c_risk == 'High Risk' or glucose_risk == 'High Risk':
                return 'High Risk'
            if a1c_risk == 'At Risk' or glucose_risk == 'At Risk':
                return 'At Risk'
            return 'Normal'

        df['BP_Risk'] = df.apply(assess_bp_risk, axis=1)
        df['HR_Risk'] = df['heart_rate'].apply(assess_hr_risk)
        df['O2_Risk'] = df['oxygen_level'].apply(assess_o2_risk)
        df['Diabetes_Risk'] = df.apply(assess_diabetes_risk, axis=1)
        
        # Overall health status
        def determine_overall_status(row):
            risks = [row['BP_Risk'], row['HR_Risk'], row['O2_Risk'], row['Diabetes_Risk']]
            if 'Critical' in risks:
                return 'Critical'
            if 'High Risk' in risks:
                return 'High Risk'
            if 'At Risk' in risks or 'Elevated' in risks:
                return 'At Risk'
            if all(r == 'Normal' for r in risks):
                return 'Normal'
            if 'No Data' in risks:
                return 'Incomplete Data'
            return 'Unknown'

        df['Health_Status'] = df.apply(determine_overall_status, axis=1)
        return df

def style_status(val):
    """Style the health status column"""
    colors = {
        'Normal': 'background-color: #28a745; color: white;',
        'At Risk': 'background-color: #ffc107; color: black;',
        'High Risk': 'background-color: #dc3545; color: white;',
        'Critical': 'background-color: #721c24; color: white;',
        'Incomplete Data': 'background-color: #6c757d; color: white;',
        'Unknown': 'background-color: #17a2b8; color: white;'
    }
    return colors.get(val, '')

def main():
    st.set_page_config(
        page_title="Patient Health Monitor",
        page_icon="🏥",
        layout="wide"
    )

    # Enhanced custom styling with modern, clean design
    st.markdown(
        """
        <style>
        /* Global Styles */
        body {
            font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
            background-color: #f4f6f9;
            color: #2c3e50;
        }

        /* Container Styles */
        .reportview-container {
            background-color: #f4f6f9;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Sidebar Styling */
        .sidebar .sidebar-content {
            background: linear-gradient(180deg, #2c3e50, #34495e);
            color: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .sidebar .stMarkdown {
            color: white !important;
        }

        /* Button Styles */
        .stButton>button {
            color: white;
            background-color: #3498db;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .stButton>button:hover {
            background-color: #2980b9;
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }

        /* Metric Card Styles */
        .stMetric {
            background-color: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }

        .stMetric:hover {
            transform: scale(1.02);
        }

        /* Metric Labels */
        .stMetric > div > div:first-child {
            color: #7f8c8d;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.85rem;
        }

        /* Metric Values */
        .stMetric > div > div:nth-child(2) {
            color: #2c3e50;
            font-weight: 700;
            font-size: 1.4rem;
        }

        /* Metric Delta */
        .stMetric > div > div:last-child {
            font-weight: 500;
        }

        /* Tabs Styling */
        .stTabs > div > div > div > div {
            background-color: white;
            border-radius: 10px;
        
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .stTabs [data-baseweb="tab-list"] {
            background-color: #ecf0f1;
            border-radius: 10px;
            padding: 5px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #324552;
            color: white;
        }

        /* DataFrame Styling */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        /* Plotly Chart Styles */
        .stPlotlyChart > div {
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.title("🏥 Patient Health Monitoring System")
    st.markdown("### Real-time Health Risk Assessment")

    # Initialize monitor (Note: You'll need to implement the PatientHealthMonitor class)
    # DBNAME = st.secrets["postgres"]["DBNAME"]
    # DBUSER = st.secrets["postgres"]["DBUSER"]
    # DBPASSWORD = st.secrets["postgres"]["DBPASSWORD"]
    # DBHOST = st.secrets["postgres"]["DBHOST"]
    # DBPORT = st.secrets["postgres"]["DBPORT"]
    monitor = PatientHealthMonitor(
        dbname=st.secrets["postgres"]["DBNAME"],
        user=st.secrets["postgres"]["DBUSER"],
        password=st.secrets["postgres"]["DBPASSWORD"],
        host=st.secrets["postgres"]["DBHOST"],
    )

    if not monitor.connect_to_database():
        st.stop()

    # Date selection
    selected_date = st.sidebar.date_input(
        "Select Analysis Date",
        value=datetime.now().date()
    )

    # Fetch and process data
    patient_data = monitor.fetch_patient_data_by_date(selected_date)
    if patient_data.empty:
        st.warning(f"No patient data available for {selected_date}")
        st.stop()

    patient_data = monitor.assess_health_risks(patient_data)

    # Filters
    st.sidebar.subheader("Filters")
    selected_gender = st.sidebar.multiselect(
        "Filter by Gender",
        options=patient_data['gender'].unique(),
        default=patient_data['gender'].unique()
    )

    # Apply filters
    filtered_data = patient_data[patient_data['gender'].isin(selected_gender)]

    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview Metrics", 
        "Patient Health Details", 
        "Health Risk Analysis", 
        "Detailed Visualizations",
        "Diabetes Analysis"
    ])

    with tab1:
        # First Row: Key Performance Indicators
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Total Patients Analyzed", 
                value=len(filtered_data),
                delta=f"Analyzed on {selected_date}"
            )
        
        with col2:
            bp_risk_count = len(filtered_data[filtered_data['BP_Risk'] == 'High Risk'])

            if bp_risk_count/len(filtered_data)*100 <= 0:
                delta_color = "normal"  # Green (default for decrease)
            else:
                delta_color = "inverse"  # Red for increase

            st.metric(
                label="BP High Risk", 
                value=bp_risk_count, 
                delta=f"{bp_risk_count/len(filtered_data)*100:.1f}% of patients",
                delta_color=delta_color
            )
        
        with col3:
            hr_risk_count = len(filtered_data[filtered_data['HR_Risk'] == 'High Risk'])

            if hr_risk_count/len(filtered_data)*100 <= 0:
                delta_color = "normal"  # Green (default for decrease)
            else:
                delta_color = "inverse"  # Red for increase

            st.metric(
                label="Heart Rate Risk", 
                value=hr_risk_count, 
                delta=f"{hr_risk_count/len(filtered_data)*100:.1f}% at risk",
                delta_color=delta_color
            )
        
        with col4:
            o2_risk_count = len(filtered_data[filtered_data['O2_Risk'] != 'Normal'])

            if o2_risk_count/len(filtered_data)*100 <= 0:
                delta_color = "normal"  # Green (default for decrease)
            else:
                delta_color = "inverse"  # Red for increase

            st.metric(
                label="Oxygen Level Risk", 
                value=o2_risk_count, 
                delta=f"{o2_risk_count/len(filtered_data)*100:.1f}% abnormal",
                delta_color=delta_color
            )
        
        with col5:
            diabetes_risk_count = len(filtered_data[filtered_data['Diabetes_Risk'] == 'High Risk'])

            if diabetes_risk_count/len(filtered_data)*100 <= 0:
                delta_color = "normal"  # Green (default for decrease)
            else:
                delta_color = "inverse"  # Red for increase

            st.metric(
                label="Diabetes High Risk", 
                value=diabetes_risk_count, 
                delta=f"{diabetes_risk_count/len(filtered_data)*100:.1f}% at risk",
                delta_color=delta_color
            )

        # Second Row: Detailed Breakdown
        st.markdown("### Detailed Patient Breakdown")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Gender Distribution
            gender_counts = filtered_data['gender'].value_counts()
            if len(gender_counts) >= 2:
                st.metric(
                    label="Gender Distribution", 
                    value=f"{gender_counts.index[0]}: {gender_counts.iloc[0]}",
                    delta=f"{gender_counts.index[1]}: {gender_counts.iloc[1]}"
                )
            else:
                st.metric(
                    label="Gender Distribution", 
                    value=f"{gender_counts.index[0]}: {gender_counts.iloc[0]}",
                    delta="No second gender"
                )
        
        with col2:
            # Age Group Analysis
            filtered_data['age_group'] = pd.cut(
                filtered_data['age'], 
                bins=[0, 18, 35, 50, 65, 100], 
                labels=['0-18', '19-35', '36-50', '51-65', '65+']
            )
            age_group_counts = filtered_data['age_group'].value_counts()
            
            if not age_group_counts.empty:
                st.metric(
                    label="Most Common Age Group Analysis", 
                    value=f"{age_group_counts.index[0]}",
                    delta=f"{age_group_counts.index[0]}: {age_group_counts.iloc[0]} patients"
                )
            else:
                st.metric(
                    label="Age Group Analysis", 
                    value="No data",
                    delta="Age groups not available"
                )
        
        with col3:
            # Critical Health Status
            if not filtered_data.empty:
                critical_count = len(filtered_data[filtered_data['Health_Status'] == 'Critical'])
                total_patients = len(filtered_data)
                
                # Avoid division by zero
                critical_percentage = (critical_count / total_patients * 100) if total_patients > 0 else 0
                
                if critical_percentage*100 <= 0:
                    delta_color = "normal"  # Green (default for decrease)
                else:
                    delta_color = "inverse"  # Red for increase

                st.metric(
                    label="Critical Health Status", 
                    value=critical_count,
                    delta=f"{critical_percentage:.1f}% of patients",
                    delta_color=delta_color
                )
            else:
                st.metric(
                    label="Critical Health Status", 
                    value="N/A",
                    delta="No patient data available"
                )
        
        with col4:
            # Incomplete Data
            incomplete_count = len(filtered_data[filtered_data['Health_Status'] == 'Incomplete Data'])
            st.metric(
                label="Incomplete Health Data", 
                value=incomplete_count,
                delta=f"{incomplete_count/len(filtered_data)*100:.1f}% require follow-up"
            )

    with tab2:
        st.header("Patient Health Details")
        
        # Prepare display columns
        display_cols = [
            'Health_Status','patient_id','first_name', 'last_name', 'gender', 'age',
            'systolic', 'diastolic', 'heart_rate', 'oxygen_level',
            'glucose_level','BP_Risk', 'HR_Risk', 'O2_Risk', 'Diabetes_Risk'
        ]
        
        # Style and display the dataframe
        styled_df = filtered_data[display_cols].style.applymap(
            style_status,
            subset=['Health_Status']
        )
        st.dataframe(styled_df, use_container_width=True)

    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            # Blood Pressure Risk Distribution
            bp_fig = px.pie(
                filtered_data,
                names='BP_Risk',
                title='Blood Pressure Risk Distribution'
            )
            st.plotly_chart(bp_fig, use_container_width=True)

            # Heart Rate Distribution
            hr_fig = px.box(
                filtered_data,
                x='gender',
                y='heart_rate',
                color='HR_Risk',
                title='Heart Rate Distribution by Gender'
            )
            st.plotly_chart(hr_fig, use_container_width=True)

            # Diabetes Risk Distribution
            diabetes_fig = px.pie(
                filtered_data,
                names='Diabetes_Risk',
                title='Diabetes Risk Distribution'
            )
            st.plotly_chart(diabetes_fig, use_container_width=True)

        with col2:
            # Oxygen Level Risk Distribution
            o2_fig = px.pie(
                filtered_data,
                names='O2_Risk',
                title='Oxygen Level Risk Distribution'
            )
            st.plotly_chart(o2_fig, use_container_width=True)

            # BP Scatter Plot
            bp_scatter = px.scatter(
                filtered_data,
                hover_data={'patient_id': True},
                x='systolic',
                y='diastolic',
                color='BP_Risk',
                title='Blood Pressure Analysis'
            )
            st.plotly_chart(bp_scatter, use_container_width=True)

    with tab4:
        st.header("Detailed Visualizations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Age Distribution
            age_dist = px.histogram(
                filtered_data, 
                x='age', 
                color='gender', 
                title='Age Distribution by Gender'
            )
            st.plotly_chart(age_dist, use_container_width=True)

        with col2:
            # Health Status Distribution
            health_status_dist = px.pie(
                filtered_data,
                names='Health_Status',
                title='Overall Health Status Distribution'
            )
            st.plotly_chart(health_status_dist, use_container_width=True)

    with tab5:
        st.header("Diabetes Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Glucose Level Scatter Plot
            glucose_scatter = px.scatter(
                filtered_data,
                hover_data={'patient_id': True},  # Include patient ID in the tooltip
                x='age',
                y='glucose_level',
                color='Diabetes_Risk',
                title='Glucose Levels by Age',
                labels={
                    'age': 'Patient Age',
                    'glucose_level': 'Glucose Level (mg/dL)'
                },
                color_discrete_map={
                    'Normal': '#28a745',
                    'At Risk': '#ffc107',
                    'High Risk': '#dc3545'
                }
            )
            
            # Customize layout for better readability
            glucose_scatter.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                margin=dict(l=50, r=50, t=50, b=50)
            )
            
            st.plotly_chart(glucose_scatter, use_container_width=True)

        with col2:
            # Diabetes Risk by Gender Pie Chart
            diabetes_gender_risk = px.pie(
                filtered_data,
                names='Diabetes_Risk',
                color='Diabetes_Risk',
                title='Diabetes Risk Distribution',
                color_discrete_map={
                    'Normal': '#28a745',
                    'At Risk': '#ffc107',
                    'High Risk': '#dc3545'
                }
            )
            
            # Customize layout
            diabetes_gender_risk.update_layout(
                font=dict(size=12),
                margin=dict(l=50, r=50, t=50, b=50)
            )
            
            st.plotly_chart(diabetes_gender_risk, use_container_width=True)

        # Additional Diabetes Insights
        st.markdown("### Diabetes Risk Insights")
        
        # Compute and display diabetes-related statistics
        diabetes_stats_col1, diabetes_stats_col2 = st.columns(2)
        
        with diabetes_stats_col1:
            # Average Glucose Level
            avg_glucose = filtered_data['glucose_level'].mean()
            st.metric(
                label="Average Glucose Level",
                value=f"{avg_glucose:.1f} mg/dL",
                delta="Across all patients"
            )

        with diabetes_stats_col2:
            # Percentage of High-Risk Diabetes Patients
            high_risk_diabetes_percentage = (len(filtered_data[filtered_data['Diabetes_Risk'] == 'High Risk']) / len(filtered_data)) * 100
            st.metric(
                label="High Diabetes Risk",
                value=f"{high_risk_diabetes_percentage:.1f}%",
                delta="of total patients"
            )

        # Optional: Diabetes Risk Correlation with Other Factors
        st.markdown("### Correlation with Other Health Factors")
        
        # Create correlation matrix for key health indicators
        correlation_columns = ['age', 'glucose_level', 'heart_rate', 'systolic', 'diastolic']
        correlation_matrix = filtered_data[correlation_columns].corr()
        
        # Visualize correlation heatmap
        correlation_heatmap = px.imshow(
            correlation_matrix, 
            text_auto=True, 
            aspect='auto', 
            title='Correlation between Health Indicators',
            color_continuous_scale='RdBu_r'
        )
        
        # Customize layout
        correlation_heatmap.update_layout(
            font=dict(size=10),
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        st.plotly_chart(correlation_heatmap, use_container_width=True)

if __name__ == "__main__":
    main()
