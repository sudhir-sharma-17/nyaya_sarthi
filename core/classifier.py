from transformers import pipeline
from typing import Dict, Any
import torch

class LegalClassifier:
    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1
        self.classifier = None
        self.model_ready = False
        self.loading = False
        self.labels = [
            "Civil", "Criminal", "Bail", "FIR", "Sexual Offence", 
            "Medical Emergency", "Property", "Domestic Violence", 
            "Labour", "Constitutional"
        ]

    def _initialize_model(self):
        if self.classifier is not None or self.loading:
            return
        
        self.loading = True
        try:
            print("Loading Legal Classification Model (BART)... This may take a few minutes on first run.")
            # Using BART large MNLI for zero-shot classification
            self.classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=self.device
            )
            self.model_ready = True
            print("Legal Classification Model Ready.")
        except Exception as e:
            print(f"Classifier model failed to load: {e}")
            self.model_ready = False
        finally:
            self.loading = False

    def classify_case(self, text: str) -> Dict[str, Any]:
        """Classify case type using zero-shot semantic understanding."""
        if not self.model_ready and not self.loading:
            self._initialize_model()

        if not self.model_ready:
            return self._keyword_fallback(text)


        try:
            # We only need the first 2000 chars for classification usually
            result = self.classifier(text[:2000], self.labels, multi_label=False)
            return {
                "case_type": result['labels'][0],
                "confidence": round(result['scores'][0], 2),
                "method": "BART Zero-Shot"
            }
        except Exception as e:
            print(f"Classification error: {e}")
            return self._keyword_fallback(text)

    def _keyword_fallback(self, text: str) -> Dict[str, Any]:
        """Simple heuristic fallback if model fails."""
        text = text.lower()
        heuristics = {
            "Sexual Offence": ["rape", "sexual assault", "pocso", "376 ipc"],
            "Bail": ["bail", "437 crpc", "438 crpc", "439 crpc"],
            "FIR": ["fir", "first information report", "police station"],
            "Medical Emergency": ["medical", "hospital", "icu", "surgery", "patient"],
            "Domestic Violence": ["domestic violence", "pwdva", "dowry"],
            "Constitutional": ["article 21", "article 32", "article 226", "writ petition"],
            "Property": ["property", "possession", "suit for", "partition"],
            "Labour": ["labour", "industrial dispute", "workman", "wages"]
        }

        for label, keywords in heuristics.items():
            if any(k in text for k in keywords):
                return {"case_type": label, "confidence": 0.5, "method": "Keyword Heuristic"}
        
        # Default based on common criminal vs civil terms
        if any(k in text for k in ["ipc", "accused", "prosecution", "offence"]):
            return {"case_type": "Criminal", "confidence": 0.4, "method": "Keyword Heuristic"}
            
        return {"case_type": "Civil", "confidence": 0.3, "method": "Default"}

legal_classifier = LegalClassifier()
