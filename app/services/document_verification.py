import os
from flask import current_app

def verify_blood_request_paper(file_path: str) -> bool | None:
    """
    Verifies if the uploaded image is a hospital blood request paper.
    Returns:
      True if verified valid
      False if rejected
      None if verification failed (e.g., API key missing, network error, lib not installed)
    """
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        current_app.logger.warning("GEMINI_API_KEY is not set. Skipping document verification.")
        
        return None
    
    if not os.path.exists(file_path):
        current_app.logger.error(f"File not found for verification: {file_path}")
       
        return None

    try:
        try:
            import google.generativeai as genai
        except ImportError:
            current_app.logger.warning("google-generativeai package not installed. Skipping verification.")
            return None

        genai.configure(api_key=api_key)
        
        # Use the standard gemini-1.5-flash model which has vision capabilities
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Upload file to Gemini API temporarily
        sample_file = genai.upload_file(path=file_path)
        
        prompt = (
            "You are a medical document verifier. "
            "Please review this image. Is it a legitimate hospital blood request form, "
            "blood requisition form, or an official medical letter requesting blood for a patient? "
            "Reply with exactly 'YES' or 'NO' followed by a brief 1 sentence reason. "
            "Do not output anything else."
        )
        
        response = model.generate_content([sample_file, prompt])
        result = response.text.strip().upper()
        
        # Clean up the file from Gemini
        try:
            genai.delete_file(sample_file.name)
        except Exception as e:
            current_app.logger.warning(f"Could not delete file from Gemini: {e}")
            
        if result.startswith("YES"):
            return True
        elif result.startswith("NO"):
            return False
        else:
            current_app.logger.warning(f"Unexpected response from Gemini: {result}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Error during document verification: {str(e)}")
        return None
