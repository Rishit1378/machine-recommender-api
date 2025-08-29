import re
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

# Initialize the Flask app and enable CORS
app = Flask(__name__)
CORS(app)

# --- Load and Preprocess Data on Startup ---
try:
    # Use pd.read_csv() and ensure the filename is an EXACT match
    machines_df = pd.read_csv("Caterpillar_Machines_Sample.xlsx - Sheet1.csv")
    
    # Standardize column names for consistency
    machines_df.rename(columns={'Payload (kg)': 'LoadCapacity'}, inplace=True)
    
    # Create required columns if they don't exist for robust filtering
    if 'Price' not in machines_df.columns:
        machines_df['Price'] = machines_df.get('Weight (kg)', 0) * 1.5 + 500000
    if 'PowerType' not in machines_df.columns:
        power_types = ['diesel', 'electric', 'hybrid']
        machines_df['PowerType'] = [power_types[i % len(power_types)] for i in range(len(machines_df))]
    if 'Description' not in machines_df.columns:
        machines_df['Description'] = "A reliable and powerful machine."

except FileNotFoundError:
    print("Error: 'Caterpillar_Machines_Sample.xlsx - Sheet1.csv' not found.")
    machines_df = pd.DataFrame()

def parse_text_regex(text: str) -> dict:
    """Extracts features from text using regular expressions."""
    text = text.lower()
    budget_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac)', text)
    load_match = re.search(r'(\d+)\s*(?:ton|tons|t)', text)
    power_match = re.search(r'(diesel|electric|hybrid)', text)
    
    budget = float(budget_match.group(1)) * 100000 if budget_match else None
    load = int(load_match.group(1)) if load_match else None
    power = power_match.group(1) if power_match else None
    
    return {"budget": budget, "load": load, "power": power}

def recommend_machine(params: dict) -> list:
    """Filters the machine dataset based on extracted parameters."""
    if machines_df.empty:
        return []
    
    df = machines_df.copy()
    
    # Convert 'LoadCapacity' from kg to tons for accurate comparison
    if 'LoadCapacity' in df.columns and df['LoadCapacity'].mean() > 1000:
        df['LoadCapacity'] = df['LoadCapacity'] / 1000

    if params.get("budget"):
        df = df[df["Price"] <= params["budget"]]
    if params.get("load"):
        df = df[df["LoadCapacity"] >= params["load"]]
    if params.get("power"):
        df = df[df["PowerType"].str.lower() == params["power"]]
        
    return df.head(3).to_dict(orient='records')

@app.route('/recommend', methods=['POST'])
def recommend_api():
    if not request.is_json or 'query' not in request.get_json():
        return jsonify({"error": "Request must be JSON with a 'query' key"}), 400
    
    query = request.get_json()['query']
    try:
        parsed_params = parse_text_regex(query)
        results = recommend_machine(parsed_params)
        return jsonify({"query": query, "extracted_parameters": parsed_params, "recommendations": results}), 200
    except Exception as e:
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500

@app.route('/')
def index():
    """A simple index route to show that the API is running."""
    return "<h1>Machine Recommendation API</h1><p>Send a POST request to /recommend to get results.</p>"

if __name__ == '__main__':
    app.run(debug=True)