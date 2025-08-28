import spacy
import re
import pandas as pd
from flask import Flask, request, jsonify

# --- NLP Model Setup (using spaCy) ---
# Load the small English language model
nlp = spacy.load("en_core_web_sm")

# Define patterns for our specific entities
patterns = [
    {"label": "BUDGET", "pattern": [{"LIKE_NUM": True}, {"LOWER": {"IN": ["lakh", "lakhs", "lac"]}}]},
    {"label": "LOAD", "pattern": [{"LIKE_NUM": True}, {"LOWER": {"IN": ["ton", "tons", "t", "tonne"]}}]},
    {"label": "POWER", "pattern": [{"LOWER": {"IN": ["diesel", "electric", "hybrid"]}}]}
]

# Add a rule-based entity recognizer to the NLP pipeline
ruler = nlp.add_pipe("entity_ruler", before="ner")
ruler.add_patterns(patterns)

# --- Flask Application Setup ---
app = Flask(__name__)

# Load and preprocess the dataset on startup
try:
    machines_df = pd.read_csv("Caterpillar_Machines_Sample.xlsx - Sheet1.csv")
    # Standardize column names
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
    print("Error: Data file not found.")
    machines_df = pd.DataFrame() # Keep an empty DataFrame to avoid crashes

def parse_text_nlp(text: str) -> dict:
    """Processes text using the spaCy pipeline to extract machine requirements."""
    doc = nlp(text.lower())
    params = {"budget": None, "load": None, "power": None}
    for ent in doc.ents:
        if ent.label_ == "BUDGET" and (num_text := re.search(r'\d+', ent.text)):
            params["budget"] = float(num_text.group(0)) * 100000
        elif ent.label_ == "LOAD" and (num_text := re.search(r'\d+', ent.text)):
            params["load"] = int(num_text.group(0))
        elif ent.label_ == "POWER":
            params["power"] = ent.text
    return params

def recommend_machine(params: dict) -> list:
    """Filters the machine dataset based on extracted parameters."""
    if machines_df.empty:
        return []
    
    df = machines_df.copy()
    
    # Convert 'LoadCapacity' from kg to tons for comparison
    if 'LoadCapacity' in df.columns and df['LoadCapacity'].mean() > 1000:
        df['LoadCapacity'] = df['LoadCapacity'] / 1000

    if params.get("budget") is not None:
        df = df[df["Price"] <= params["budget"]]
    if params.get("load") is not None:
        df = df[df["LoadCapacity"] >= params["load"]]
    if params.get("power") is not None:
        df = df[df["PowerType"].str.lower() == params["power"]]
        
    return df.head(3).to_dict(orient='records')

# --- API Endpoint Definition ---
@app.route('/recommend', methods=['POST'])
def recommend_api():
    """
    API endpoint to get machine recommendations.
    Expects a JSON payload with a "query" key.
    e.g., {"query": "show me a 10 ton diesel machine under 15 lakhs"}
    """
    # Check if the request contains JSON data
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    query = data.get('query')

    # Check if the 'query' key is present
    if not query:
        return jsonify({"error": "Missing 'query' key in request body"}), 400

    try:
        # Process the query and get recommendations
        parsed_params = parse_text_nlp(query)
        results = recommend_machine(parsed_params)
        
        # Return the results as a JSON response
        return jsonify({
            "query": query,
            "extracted_parameters": parsed_params,
            "recommendations": results
        }), 200

    except Exception as e:
        # Handle any internal errors
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500

@app.route('/')
def index():
    """A simple index route to show that the API is running."""
    return "<h1>Machine Recommendation API</h1><p>Send a POST request to /recommend to get results.</p>"

if __name__ == '__main__':
    app.run(debug=True)