from flask import Flask, request, jsonify
import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
import models
import s3data
import time
import os
import requests 
import dotenv

dotenv.load_dotenv()

# loads the "darkly" template and sets it as the default
load_figure_template("darkly")

server = Flask(__name__) 
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.DARKLY])


app.layout = html.Div([
    dbc.Container( children=[
        html.Div(id="app-container", style={"width": "512px", "margin": "0 auto", "padding": "0px"},children=[
            # html.H2("Webcam Capture with Dash", id="my-header", className="mb-4 text-center"),
            dbc.Row([
                dbc.Col([
                    dcc.Dropdown(
                        options=[], # populated via callback
                        id='model-selection', 
                        className="mb-3", 
                        placeholder="Select a validation model...",
                        searchable=False,
                        clearable=True,
                        closeOnSelect=True,
                        persistence=True,
                        persistence_type="session",
                    )
                ], width=12)
            ]),
            html.Div(id="live-feed", children=[
                html.Div(id="video-container", className="mb-3"),
                dbc.ButtonGroup([
                    dbc.Button("Classify", id="classify-btn", color="primary", className="me-2"),
                    dbc.Button("Validate", id="validate-btn", color="success", className="me-2"),
                    dbc.Button("Capture Frame", id="capture-btn", color="warning"),
                ], className="d-flex justify-content-center mb-3"),
            ]),
            html.Div(id="capture-panel", style={"display": "none"}, children=[
                dbc.Row([
                    dbc.Col([
                        html.Img(id="captured-image", src="", className="captured-frame mb-3"),
                    ], width=12, className="text-center")
                ]),
                dbc.ButtonGroup([
                    dbc.Button("Normal", id="normal-data-btn", color="success", className="me-2"),
                    dbc.Button("Anomaly", id="anomaly-data-btn", color="danger", className="me-2"),
                    dbc.Button("Discard", id="discard-btn", color="secondary"),
                ], className="d-flex justify-content-center"),
            ]),
            html.Div(id="classification-result-panel", style={"display": "none"}, children=[
                dbc.Row([
                    dbc.Col([
                        html.Img(id="classification-result-image", src="", className="captured-frame mb-3"),
                        html.Div(id="classification-result-text", className="mb-3 text-center"),
                    ], width=12, className="text-center")
                ]),
                dbc.ButtonGroup([
                    dbc.Button("Dismiss", id="dismiss-classification-btn", color="secondary"),
                ], className="d-flex justify-content-center"),
            ]),
            html.Div(id="validation-result-panel", style={"display": "none"}, children=[
                dbc.Row([
                    dbc.Col([
                        html.Img(id="validation-result-image", src="", className="captured-frame mb-3"),
                        html.Div(id="validation-result-text", className="mb-3 text-center"),
                        html.Div(id="selected-model-text", className="mb-3 text-center text-muted"),
                    ], width=12, className="text-center")
                ]),
                dbc.ButtonGroup([
                    dbc.Button("Dismiss", id="dismiss-validation-btn", color="secondary"),
                ], className="d-flex justify-content-center"),
            ]),
        ]),
    ], fluid=False, className="py-4"),
    
    html.Script(src="/assets/webcam.js"),

])

captured_frame = None

def reset_to_live_feed():
    print("Resetting to live feed")
    return [{"display": "none"}, {"display": "block"}, {"display": "none"}, {"display": "none"}]

def show_capture_panel():
    print("Showing capture panel")
    return [{"display": "block"}, {"display": "none"}, {"display": "none"}, {"display": "none"}]

def show_classification_result_panel():
    print("Showing classification result panel")
    return [{"display": "none"}, {"display": "none"}, {"display": "block"}, {"display": "none"}]

def show_validation_result_panel():
    print("Showing validation result panel")
    return [{"display": "none"}, {"display": "none"}, {"display": "none"}, {"display": "block"}]

# On page reload
@callback(
    Output('model-selection', 'options'),
    Input('app-container', 'children')
)
def update_model_choices(_):
    """Update model choices whenever the page loads"""
    return models.get_model_choices("name LIKE '%Anomaly'")

@callback(
    [Output("capture-panel", "style"),
     Output("live-feed", "style"),
     Output("classification-result-panel", "style"),
     Output("validation-result-panel", "style"),
     Output("classification-result-image", "src"),
     Output("classification-result-text", "children"),
     Output("validation-result-image", "src"),
     Output("validation-result-text", "children"),
     Output("selected-model-text", "children")],
    [Input("capture-btn", "n_clicks"),
     Input("discard-btn", "n_clicks"),
     Input("classify-btn", "n_clicks"),
     Input("validate-btn", "n_clicks"),
     Input("dismiss-classification-btn", "n_clicks"),
     Input("dismiss-validation-btn", "n_clicks"),
     Input("model-selection", "value")],
    prevent_initial_call=True
)
def handle_panel_visibility(capture_clicks, discard_clicks, classify_clicks, validate_clicks, 
                          dismiss_classification_clicks, dismiss_validation_clicks, selected_model):
    global captured_frame
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if triggered_id == "capture-btn":
        time.sleep(0.01)  # Wait for javascript to process first
        if captured_frame:
            print("Captured frame exists, updating panel style")
            return show_capture_panel() + [dash.no_update] * 5
        else:
            return reset_to_live_feed() + [dash.no_update] * 5
    
    elif triggered_id == "discard-btn":
        print("Discarding capture")
        captured_frame = None
        return reset_to_live_feed() + [dash.no_update] * 5
    
    elif triggered_id == "dismiss-classification-btn":
        print("Dismissing classification result")
        return reset_to_live_feed() + [dash.no_update] * 5
        
    elif triggered_id == "dismiss-validation-btn":
        print("Dismissing validation result")
        return reset_to_live_feed() + [dash.no_update] * 5
        
    elif triggered_id == "validate-btn":
        if captured_frame:
            print("Validating capture")
            try:
                model_text = f"Selected Model: {selected_model}" if selected_model else "No model selected"
                validation_text = "Validation result: Normal (placeholder)"
                validation_image = captured_frame  # Store image for display
                
                validation_panels = show_validation_result_panel()
                captured_frame = None  # Clear the captured frame after validation
                return validation_panels + [dash.no_update, dash.no_update, validation_image, validation_text, model_text]
                
            except Exception as e:
                print("Validation Error:", e)
                model_text = f"Selected Model: {selected_model}" if selected_model else "No model selected"
                validation_image = captured_frame
                validation_panels = show_validation_result_panel()
                captured_frame = None
                return validation_panels + [dash.no_update, dash.no_update, validation_image, f"Validation Error: {str(e)}", model_text]
        
    elif triggered_id == "classify-btn":
        if captured_frame:
            print("Classifying capture")
            try:
                resp = requests.post(
                    "http://localhost:8000/predict",
                    json={"image": captured_frame}
                )
                response_data = resp.json()
                print("Response from classification API:", response_data)
                
                # Extract classification result
                classification_text = f"Classification: {response_data.get('prediction', 'Unknown')}"
                if 'confidence' in response_data:
                    classification_text += f" (Confidence: {response_data['confidence']:.2%})"
                
                classification_panels = show_classification_result_panel()
                return classification_panels + [captured_frame, classification_text, dash.no_update, dash.no_update, dash.no_update]
                
            except Exception as e:
                print("Error:", e)
                classification_panels = show_classification_result_panel()
                return classification_panels + [captured_frame, f"Classification Error: {str(e)}", dash.no_update, dash.no_update, dash.no_update]

    return dash.no_update

@callback(
    [Output("capture-panel", "style", allow_duplicate=True),
     Output("live-feed", "style", allow_duplicate=True),
     Output("classification-result-panel", "style", allow_duplicate=True),
     Output("validation-result-panel", "style", allow_duplicate=True)],
    [Input("normal-data-btn", "n_clicks"),
     Input("anomaly-data-btn", "n_clicks"),
     Input("model-selection", "value")],
    prevent_initial_call=True
)
def handle_data_uploads(normal_clicks, anomaly_clicks, selected_model):
    global captured_frame
    
    ctx = dash.callback_context
    if not ctx.triggered or not captured_frame:
        return dash.no_update
    
    if not selected_model:
        print("No model selected for data upload")
        return dash.no_update
    
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if triggered_id == "normal-data-btn":
        category = 'good'
        prefix = 'normal'
        split = 'train'
        print("Normal data capture")
    elif triggered_id == "anomaly-data-btn":
        category = 'anomaly'
        prefix = 'anomaly'
        split = 'test'
        print("Anomaly data capture")
    else:
        return dash.no_update
    
    main_category = selected_model
    
    # Upload to S3
    image_bytes = s3data.base64_dataurl_to_bytes(captured_frame)
    success = s3data.upload_data_to_s3(
        bucket_name=os.getenv('BUCKET_NAME'),
        local_path=None,
        main_category=main_category,
        split=split,
        category=category,
        image_bytes=image_bytes,
        filename=f"{prefix}_{int(time.time())}.jpg"
    )
    
    if success:
        print(f"{prefix.capitalize()} data uploaded successfully")
    else:
        print(f"Failed to upload {prefix} data")
    
    captured_frame = None
    return reset_to_live_feed()

@server.route('/capture-frame', methods=['POST'])
def capture_frame():
    image = request.json.get('image')
    if not image:
        print ("No image data received")
        return jsonify({"error": "No image data provided"}), 400
    print("Received image data")
    global captured_frame
    captured_frame = image
    
    return jsonify({"status": "received"})

if __name__ == "__main__":
    if os.getenv('DASH_DEBUG', 'false').lower() == 'true':
        app.run(debug=True)
    else:
        from waitress import serve
        print("Starting production server with Waitress on port 8050...")
        serve(server, host='0.0.0.0', port=8050)
