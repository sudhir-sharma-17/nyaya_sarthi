import io
import json
import pdfplumber
import pytesseract
import fitz  # PyMuPDF
import re
import dateparser
import spacy
from PIL import Image
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.config import settings

try:
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    print(f"Warning: spaCy model en_core_web_sm failed to load: {e}")
    nlp = None

from langchain_ollama import OllamaLLM
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

from core.research import legal_research

class CaseSchema(BaseModel):
    case_title: str = Field(description="Descriptive case title inferred from parties or matter (e.g., 'Amir Hussain vs State of U.P.')")
    petitioner: str = Field(description="Name of the petitioner or appellant")
    respondent: str = Field(description="Name of the respondent")
    court_name: str = Field(description="Name of the court (e.g., Allahabad High Court)")
    filing_date: str = Field(description="Date of filing if available, or 'Inferred from context'")
    case_type: str = Field(description="One of: Bail, Criminal, Civil, Domestic Violence, Property, Juvenile, Writ, Constitutional")
    relief_sought: str = Field(description="The primary relief or prayer requested by the petitioner")
    legal_issue: str = Field(description="The core legal issue or question of law involved")
    statutes_sections: List[str] = Field(description="List of relevant Statutes, Acts, or IPC Sections mentioned")
    legal_summary: str = Field(description="A concise legal summary generated from the extracted text")
    priority_reasoning: str = Field(description="Case-specific reasoning for prioritization (e.g., 'Bail delay and personal liberty issue')")
    clustering_compatibility: str = Field(description="Type of cases this can be grouped with (e.g., 'Bail/Criminal')")
    scheduling_compatibility: str = Field(description="Urgency/Type for scheduling (e.g., 'Urgent/Constitutional')")
    urgency_score: int = Field(description="0-100 based on legal features")
    confidence_score: int = Field(description="0-100 based on extraction completeness")
    recommended_priority: str = Field(description="High, Medium, or Low")

class IntelligenceEngine:
    def __init__(self):
        self.ollama_llm = None
        try:
            self.ollama_llm = OllamaLLM(
                model=settings.LLM_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                format="json"
            )
        except Exception as e:
            print(f"[IntelligenceEngine] Ollama unavailable: {e}")

        self.groq_llm = None
        try:
            if settings.GROQ_API_KEY:
                self.groq_llm = ChatGroq(
                    groq_api_key=settings.GROQ_API_KEY,
                    model_name=settings.GROQ_MODEL,
                    response_format={"type": "json_object"}
                )
        except Exception as e:
            print(f"[IntelligenceEngine] Groq unavailable: {e}")

        self.llm = self.groq_llm if self.groq_llm else self.ollama_llm

    async def extract_case_info(self, file_content: bytes, file_name: str) -> Dict[str, Any]:
        """
        Robust 8-stage hybrid extraction pipeline:
        1. PyMuPDF Extraction
        2. Text Quality Validation
        3. OCR Fallback (if needed)
        4. Text Cleaning & Normalization
        5. Regex Metadata Extraction
        6. spaCy NLP Entity Detection
        7. Semantic Inference Layer
        8. Structured JSON Output
        """
        # 1. PyMuPDF text extraction
        text, method = self._robust_extract_text(file_content, file_name)
        
        # 2 & 3. Text Quality Validation & OCR Fallback
        if self._is_text_garbage_or_insufficient(text):
            print(f"[IntelligenceEngine] Extracted text from {file_name} is garbage or too short. Launching OCR fallback...")
            ocr_text = self._ocr_pdf(file_content)
            if len(ocr_text.strip()) > 100:
                text = ocr_text
                method = "Tesseract OCR (Fallback)"
        
        # 4. Text Cleaning & Normalization
        text = self._clean_text(text)
        
        # 5. Regex Metadata Extraction
        regex_meta = self._extract_regex_metadata(text)
        
        # 6. spaCy NLP Entity Detection
        nlp_entities = self._extract_nlp_entities(text)
        
        # 7. Semantic Inference Layer
        extracted = self._semantic_inference(text, regex_meta, nlp_entities, file_name)
        
        # 8. Add extra fields and ensure compatibility with backend / upload routes
        extracted["full_text"] = text
        extracted["extraction_method"] = method
        extracted["extracted_length"] = len(text)
        
        # Date extraction
        robust_dates = self._extract_dates_robustly(text)
        extracted["filing_date"] = robust_dates["filing_date"]
        extracted["hearing_date"] = robust_dates["hearing_date"]
        if extracted.get("judgment_date") == "Not Available" or not extracted.get("judgment_date"):
            extracted["judgment_date"] = robust_dates["judgment_date"]
            
        # Outcome extraction
        extracted["final_outcome"] = self._extract_legal_outcome(text)
        extracted["legal_outcome"] = extracted["final_outcome"]
        
        # Legal issue fallback
        extracted["legal_issue"] = regex_meta.get("legal_issue") or self._extract_legal_issue_fallback(text)
        extracted["core_legal_issue"] = extracted["legal_issue"]
        
        # Summary fallback / generation
        # We can try LLM summaries first if LLM is enabled
        llm_summary = None
        if self.llm and len(text) > 100:
            try:
                llm_input = text[:6000]
                if len(text) > 7000:
                    llm_input += "\n\n[... MID SECTION OMITTED ...]\n\n" + text[-3000:]
                prompt = PromptTemplate(
                    template="""
                    Analyze this Indian court judgment and return a 4-6 line case summary.
                    Return JSON only format:
                    {{"summary": "Summary text..."}}
                    
                    ### TEXT:
                    {text}
                    """,
                    input_variables=["text"]
                )
                response = self.llm.invoke(prompt.format(text=llm_input))
                res_text = response.content if hasattr(response, 'content') else str(response)
                start = res_text.find('{')
                end = res_text.rfind('}')
                if start != -1 and end != -1:
                    llm_json = json.loads(res_text[start:end+1])
                    llm_summary = llm_json.get("summary")
            except Exception as e:
                print(f"LLM Summary generation failed: {e}")
                
        extracted["summary"] = llm_summary or self._generate_fallback_summary(extracted)
        extracted["legal_summary"] = extracted["summary"]
        
        # Statutes and sections list compatibility
        extracted["acts"] = extracted.get("statutes", [])
        extracted["sections"] = []
        
        # Sanitize and finalize metadata integrity
        return self._ensure_metadata_integrity(extracted, text)

    def _robust_extract_text(self, content: bytes, file_name: str) -> tuple[str, str]:
        """Primary extraction using PyMuPDF, with pdfplumber fallback."""
        text = ""
        method = "None"
        if not file_name.lower().endswith(".pdf"):
            text = self._extract_from_image(content)
            return text, "Tesseract OCR (Image)"

        # PyMuPDF (Fitz)
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            method = "PyMuPDF"
            if len(text.strip()) > 1000:
                return text, "PyMuPDF"
        except Exception as e:
            print(f"PyMuPDF error: {e}")

        # pdfplumber fallback
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages[:10]:
                    text += page.extract_text() or ""
            method = "pdfplumber"
        except Exception as e:
            print(f"pdfplumber error: {e}")
            
        return text, method

    def _is_text_garbage_or_insufficient(self, text: str) -> bool:
        """Validate if the extracted text is insufficient or garbage to trigger OCR fallback."""
        if not text or len(text.strip()) < 1000:
            return True
        alpha_chars = sum(c.isalpha() for c in text)
        if len(text) > 0 and (alpha_chars / len(text)) < 0.4:
            return True
        return False

    def _ocr_pdf(self, content: bytes) -> str:
        """Automatically render PDF pages into images and run Tesseract OCR."""
        ocr_text = ""
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            # Scan first 5 pages only to maintain performance while extracting metadata
            for page in doc[:5]:
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                ocr_text += pytesseract.image_to_string(img) + "\n"
            doc.close()
        except Exception as e:
            print(f"Tesseract OCR fallback failed: {e}")
        return ocr_text

    def _clean_text(self, text: str) -> str:
        """Removes headers, footers, excessive whitespace, and normalize fragments."""
        text = re.sub(r'(?i)page\s+\d+(?:\s+of\s+\d+)?', '', text)
        text = re.sub(r'(?i)\b\d+\s+of\s+\d+\b', '', text)
        text = re.sub(r'(?i)court\s+no\s*\.?\s*\d+.*?(?:\n|$)', '', text)
        text = re.sub(r'(?i)in\s+the\s+court\s+of.*?(?:\n|$)', '', text)
        
        lines = []
        for line in text.split('\n'):
            line = re.sub(r'[ \t]+', ' ', line).strip()
            if line:
                lines.append(line)
                
        merged_lines = []
        for line in lines:
            if not merged_lines:
                merged_lines.append(line)
                continue
            
            prev_line = merged_lines[-1]
            is_prev_fragment = False
            if prev_line:
                last_char = prev_line[-1]
                if last_char in [',', ';', '-', '(']:
                    is_prev_fragment = True
                else:
                    last_word_match = re.search(r'\b(\w+)\s*$', prev_line)
                    if last_word_match:
                        last_word = last_word_match.group(1).lower()
                        if last_word in ['and', 'or', 'of', 'the', 'in', 'to', 'for', 'with', 'by', 'at', 'on', 'from', 'as']:
                            is_prev_fragment = True
            
            is_curr_continuation = False
            if line:
                first_char = line[0]
                if first_char.islower():
                    is_curr_continuation = True
                elif not re.match(r'^(?:PETITIONER|RESPONDENT|BENCH|CORAM|JUDGES|AUTHOR|JUDGMENT|COURT|CASE|APPELLANT|DEFENDANT)\b', line, re.IGNORECASE):
                    if is_prev_fragment and len(prev_line) < 80:
                        is_curr_continuation = True
            
            if is_prev_fragment and is_curr_continuation:
                merged_lines[-1] = prev_line + " " + line
            else:
                merged_lines.append(line)
                
        cleaned_text = '\n'.join(merged_lines)
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        cleaned_text = re.sub(r'\n+', '\n', cleaned_text)
        return cleaned_text.strip()

    def _extract_regex_metadata(self, text: str) -> Dict[str, Any]:
        """Uses regex pattern matching to parse court metadata."""
        meta = {}
        
        # 1. Author
        author_patterns = [
            r'(?i)(?:Authoring\s+Judge|Author|AUTHOR|Delivered\s+by)\s*[:\-]?\s*([A-Z][A-Za-z\s\.,\(\)]+?)(?:\n|$)',
            r'\b([A-Z][A-Za-z\s\.,\(\)]+?)\s*,\s*(?:J\.|C\.?J\.|Justice)\s+delivering\s+the\s+judgment\b'
        ]
        meta["author"] = "Not Available"
        for pat in author_patterns:
            m = re.search(pat, text)
            if m:
                meta["author"] = self._normalize_judge_name(m.group(1))
                break
                
        # 2. Bench (supports multiline)
        bench_patterns = [
            r'(?i)\b(?:BENCH|CORAM|PRESENT|BEFORE|JUDGES)\b\s*[:\-]?\s*\n?((?:[A-Z\s\.,\'\-\(\)]+\n?){1,5})'
        ]
        meta["bench"] = []
        for pat in bench_patterns:
            m = re.search(pat, text)
            if m:
                bench_block = m.group(1).strip()
                normalized = self._normalize_multiline_bench(bench_block)
                if normalized and normalized != "Not Available":
                    meta["bench"] = [j.strip() for j in normalized.split(",") if j.strip()]
                    break
                    
        # 3. Petitioner
        pet_patterns = [
            r'(?i)\b(?:PETITIONER|Appellant)\s*[:\-]?\s*([A-Z][A-Za-z\s\.,\'\-&\(\)]+)(?:\n|$)'
        ]
        meta["petitioner"] = "Not Available"
        for pat in pet_patterns:
            m = re.search(pat, text)
            if m:
                meta["petitioner"] = m.group(1).strip()
                break
                
        # 4. Respondent
        resp_patterns = [
            r'(?i)\b(?:RESPONDENT|Respondents|Respondent)\s*[:\-]?\s*([A-Z][A-Za-z\s\.,\'\-&\(\)]+)(?:\n|$)'
        ]
        meta["respondent"] = "Not Available"
        for pat in resp_patterns:
            m = re.search(pat, text)
            if m:
                meta["respondent"] = m.group(1).strip()
                break
                
        # 5. Court
        court_patterns = [
            r'(?i)\b(Supreme\s+Court\s+of\s+India|High\s+Court\s+of\s+[A-Za-z\s]+)\b',
            r'(?i)\b([A-Za-z\s]+\s+High\s+Court)\b'
        ]
        meta["court"] = "Not Available"
        for pat in court_patterns:
            m = re.search(pat, text)
            if m:
                meta["court"] = m.group(1).strip()
                break
                
        # 6. Judgment Date
        date_patterns = [
            r'(?i)(?:DATE\s+OF\s+JUDGMENT|Judgment\s+delivered\s+on|Dated?)\s*[:\-]?\s*([A-Z0-9\s\.,\-/]+)(?:\n|$)'
        ]
        meta["judgment_date"] = "Not Available"
        for dp in date_patterns:
            dm = re.search(dp, text)
            if dm:
                try:
                    parsed = dateparser.parse(
                        dm.group(1).strip(),
                        settings={'STRICT_PARSING': True, 'REQUIRE_PARTS': ['day', 'month', 'year']}
                    )
                    if parsed:
                        meta["judgment_date"] = parsed.strftime("%Y-%m-%d")
                        break
                except:
                    pass
                    
        return meta

    def _normalize_multiline_bench(self, bench_str: str) -> str:
        """Standardizes multiline judge names from BENCH block."""
        lines = [line.strip() for line in bench_str.split("\n") if line.strip()]
        judges = []
        for line in lines:
            line_clean = self._normalize_judge_name(line)
            if not line_clean or len(line_clean) < 3 or len(line_clean) > 60:
                continue
            
            # Format "LASTNAME, F.M." -> "F.M. Lastname"
            comma_parts = line_clean.split(",")
            if len(comma_parts) == 2:
                last = comma_parts[0].strip().title()
                first = comma_parts[1].strip().upper()
                if len(first.replace(".", "")) <= 5:
                    line_clean = f"{first} {last}"
                else:
                    line_clean = f"{first.title()} {last}"
            else:
                line_clean = line_clean.title()
                
            if line_clean.lower() not in [j.lower() for j in judges] and not any(w in line_clean.lower() for w in ["court", "vs", "versus", "appeal", "petitioner", "respondent"]):
                judges.append(line_clean)
        return ", ".join(judges) if judges else "Not Available"

    def _extract_nlp_entities(self, text: str) -> Dict[str, List[str]]:
        """Run spaCy named entity recognition to identify candidate judges, courts, and dates."""
        entities = {"PERSON": [], "ORG": [], "DATE": []}
        if not nlp:
            return entities
        # Process the first 10,000 characters for high-density metadata region
        doc = nlp(text[:10000])
        for ent in doc.ents:
            if ent.label_ in entities:
                val = ent.text.strip().replace("\n", " ")
                val = re.sub(r'\s+', ' ', val)
                if len(val) > 2 and val not in entities[ent.label_]:
                    entities[ent.label_].append(val)
        return entities

    def _semantic_inference(self, text: str, regex_meta: Dict[str, Any], nlp_entities: Dict[str, List[str]], file_name: str) -> Dict[str, Any]:
        """Leverages context, spaCy entities, and surrounding layout structure to infer missing metadata."""
        meta = regex_meta.copy()
        
        # 1. Petitioner / Respondent inference from Vs. pattern
        title_inferred = "Not Available"
        vs_match = re.search(
            r'^([A-Z][^\n]{2,80}?)\s+(?:vs?\.?|versus)\s+([A-Z][^\n]{2,80})',
            text, re.IGNORECASE | re.MULTILINE
        )
        if vs_match:
            title_inferred = vs_match.group(0).strip()
            pet_inferred = vs_match.group(1).strip()
            resp_inferred = vs_match.group(2).strip()
        else:
            pet_inferred = "Not Available"
            resp_inferred = "Not Available"
            
        if meta.get("petitioner") == "Not Available" or not meta.get("petitioner"):
            meta["petitioner"] = pet_inferred
        if meta.get("respondent") == "Not Available" or not meta.get("respondent"):
            meta["respondent"] = resp_inferred
            
        if meta["petitioner"] != "Not Available" and meta["respondent"] != "Not Available":
            meta["case_title"] = f"{meta['petitioner']} vs {meta['respondent']}"
        elif title_inferred != "Not Available":
            meta["case_title"] = title_inferred
        else:
            # Fallback to Title Cased file name
            meta["case_title"] = file_name.replace(".pdf", "").replace("_", " ").title()
            
        # 2. Court name inference from headers & ORGs
        if meta.get("court") == "Not Available" or not meta.get("court"):
            for org in nlp_entities.get("ORG", []):
                if any(kw in org.lower() for kw in ["supreme court", "high court"]):
                    meta["court"] = org.title()
                    break
            if meta["court"] == "Not Available":
                lines = [l.strip() for l in text.split("\n") if l.strip()][:30]
                for l in lines:
                    if "supreme court" in l.lower():
                        meta["court"] = "Supreme Court of India"
                        break
                    elif "high court" in l.lower():
                        hc_match = re.search(r'\b(High\s+Court\s+of\s+[A-Za-z\s]+)\b', l, re.IGNORECASE)
                        if hc_match:
                            meta["court"] = hc_match.group(1).title()
                            break
                        meta["court"] = l.title()
                        break
                        
        if meta.get("court") != "Not Available":
            meta["court"] = self._normalize_court_name(meta["court"])
            
        meta["court_name"] = meta["court"]
        
        # 3. Infer Bench / Judges from spaCy PERSONs
        if not meta.get("bench"):
            judges = []
            for p in nlp_entities.get("PERSON", []):
                if any(marker in p.lower() for marker in ["justice", "judge"]) or re.search(r'\b(?:J\.|C\.?J\.)', p):
                    name = self._normalize_judge_name(p)
                    if name and len(name) > 3 and name.lower() not in [j.lower() for j in judges]:
                        judges.append(name.title())
            meta["bench"] = judges
            
        # 4. Infer Author from first judge on Bench or top PERSONs
        if meta.get("author") == "Not Available" or not meta.get("author"):
            if meta.get("bench"):
                meta["author"] = meta["bench"][0]
            else:
                author_nlp = [p for p in nlp_entities.get("PERSON", []) if any(marker in p.lower() for marker in ["justice", "judge"])]
                if author_nlp:
                    meta["author"] = self._normalize_judge_name(author_nlp[0])
                    
        # Citations
        citations = []
        inline_cits = re.findall(
            r'\b(?:AIR|SCC|SCR|Cr\.?LJ|All\.?LJ|SCALE|SLT)\s+\d{4}\s+\w+\s+\d+\b',
            text
        )
        if inline_cits:
            citations = list(dict.fromkeys(inline_cits))[:15]
        meta["citations"] = citations
        
        # Statutes
        statutes = []
        statute_matches = re.findall(
            r'(?:Section|S\.)\s+\d+(?:\([a-z0-9]+\))?(?:\s+of\s+(?:the\s+)?[A-Z][^,\n]{3,60})?'
            r'|Article\s+\d+(?:\([a-z0-9]+\))?(?:\s+of\s+(?:the\s+)?[A-Z][^,\n]{3,60})?'
            r'|[A-Z][a-zA-Z\s]+Act,?\s+\d{4}',
            text
        )
        if statute_matches:
            seen = []
            for s in statute_matches:
                clean = s.strip()
                if clean and clean not in seen and len(clean) < 120:
                    seen.append(clean)
            statutes = seen[:20]
        meta["statutes"] = statutes
        
        # Case Number
        case_num = "Not Available"
        case_patterns = [
            r'(?:Case|W\.P\.|Crl\.A\.|O\.S\.|M\.A\.)\s*No\.?\s*([A-Z0-9\-/]+(?:\s*of\s*\d{4})?)',
            r'(?:No\.?)\s*([A-Z0-9\-/]+\s*of\s*\d{4})',
            r'([A-Z]+\s*/\s*\d+\s*/\s*\d{4})'
        ]
        for pattern in case_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                case_num = match.group(1).strip()
                break
        meta["case_number_extracted"] = case_num
        
        return meta

    def _extract_legal_issue_fallback(self, text: str) -> str:
        """Infers the core legal issue when not explicitly extracted by LLM."""
        issue_match = re.search(r'\b(?:issue|question\s+of\s+law|dispute)\s+(?:involved|is|are|whether)\s+([^.\n]{10,200}\b)', text[:6000], re.IGNORECASE)
        if issue_match:
            return issue_match.group(0).strip()
        return "Whether the petition is maintainable under the circumstances of the case."

    def _generate_fallback_summary(self, meta: Dict[str, Any]) -> str:
        """Fills in a template-based summary from extracted metadata if AI is unavailable."""
        parts = []
        if meta.get("case_title") != "Not Available":
            parts.append(f"This is the case of {meta['case_title']}.")
        if meta.get("court") != "Not Available":
            parts.append(f"Heard before the {meta['court']}.")
        if meta.get("bench"):
            judges_str = ", ".join(meta["bench"])
            parts.append(f"The bench comprised of {judges_str}.")
        if meta.get("judgment_date") != "Not Available":
            parts.append(f"Judgment was delivered on {meta['judgment_date']}.")
        if not parts:
            return "Legal intelligence summary pending full judicial review."
        return " ".join(parts)

    def _ensure_metadata_integrity(self, data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Performs logical and type constraints checks on final output schema."""
        if not data: data = {}
        
        # 1. Strictly Sanitize All Metadata Fields
        data["case_title"] = self._sanitize_field(data.get("case_title"), "title")
        data["case_number_extracted"] = self._sanitize_field(data.get("case_number_extracted"), "case_id")
        data["petitioner"] = self._sanitize_field(data.get("petitioner"), "party")
        data["respondent"] = self._sanitize_field(data.get("respondent"), "party")
        data["court_name"] = self._sanitize_field(data.get("court_name"), "court")
        
        # Normalization of Bench representation
        bench_data = data.get("bench")
        if isinstance(bench_data, list):
            bench_str = ", ".join(bench_data) if bench_data else "Not Available"
        else:
            bench_str = str(bench_data or "Not Available")
        
        sanitized_bench = self._sanitize_field(bench_str, "bench")
        if sanitized_bench != "Not Available" and sanitized_bench:
            data["bench"] = [j.strip() for j in sanitized_bench.split(",") if j.strip()]
        else:
            data["bench"] = []
            
        # 2. Extract Legal Outcome if missing
        if not data.get("legal_outcome") or data.get("legal_outcome") == "Not Available" or len(str(data.get("legal_outcome"))) > 300:
            data["legal_outcome"] = self._extract_legal_outcome(raw_text)
        data["final_outcome"] = data["legal_outcome"]

        # 3. Ensure Summary is reasonable
        summary = data.get("summary", "")
        if not summary or "pending full summarization" in str(summary).lower() or len(str(summary)) < 30:
            data["summary"] = "Not Available"
        elif len(str(summary)) > 2000:
            data["summary"] = str(summary)[:2000] + "..."
        data["legal_summary"] = data["summary"]

        # 4. Standardize Case Type
        if not data.get("case_type_inferred") or data.get("case_type_inferred") == "Not Available":
             data["case_type_inferred"] = "General"

        # 5. Date Parsing & Chronological Validation
        date_fields = ["filing_date", "judgment_date", "hearing_date"]
        parsed_dates = {}
        for df in date_fields:
            d_val = data.get(df, "")
            if re.match(r'\d{4}-\d{2}-\d{2}', str(d_val)):
                try:
                    from datetime import datetime
                    parsed_dates[df] = datetime.strptime(str(d_val), "%Y-%m-%d")
                except: pass
            else:
                data[df] = "Not Available"

        # Validate: Filing Date cannot be later than Judgment Date
        if parsed_dates.get("filing_date") and parsed_dates.get("judgment_date"):
            if parsed_dates["filing_date"] > parsed_dates["judgment_date"]:
                data["filing_date"] = "Not Available"
                print(f"Discarding invalid filing date (later than judgment): {data['filing_date']}")
            elif (parsed_dates["judgment_date"].year - parsed_dates["filing_date"].year) > 50:
                data["filing_date"] = "Not Available"
                print(f"Discarding invalid filing date (too old, >50 yrs anomaly): {data['filing_date']}")

        # Recalculate Urgency if missing or generic
        current_urgency = data.get("urgency_score", 0)
        if not current_urgency or current_urgency == 0 or current_urgency == 50:
            heuristics = {
                "death penalty": 98, "capital punishment": 98, "habeas corpus": 95,
                "bail": 85, "anticipatory bail": 88, "quashing": 75,
                "interim stay": 80, "injunction": 78, "eviction": 72,
                "senior citizen": 65, "pension": 60, "matrimonial": 55,
                "service matter": 45, "taxation": 40, "commercial": 35
            }
            score = 30
            text_lower = raw_text.lower()
            for kw, s in heuristics.items():
                if kw in text_lower: score = max(score, s)
            
            if any(w in text_lower for w in ["urgent", "emergency", "immediate", "expedite"]):
                score = min(score + 10, 100)
                
            data["urgency_score"] = score

        return data

    def _sanitize_field(self, value: Any, field_type: str = "generic") -> str:
        """Cleans, validates and normalises a single metadata field value.

        Args:
            value:      Raw extracted value (str, list, None, …).
            field_type: One of 'title', 'party', 'court', 'bench', 'case_id', 'generic'.

        Returns:
            A clean string, or 'Not Available' when the value is unusable.
        """
        FALLBACK = "Not Available"

        # ── Coerce to string ──────────────────────────────────────────────────
        if value is None:
            return FALLBACK
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if v)
        value = str(value).strip()

        # ── Reject obviously bad values ───────────────────────────────────────
        bad_tokens = {
            "not available", "n/a", "na", "none", "null", "unknown",
            "not found", "not specified", "not mentioned", "not stated",
            "not determined", "not applicable", "not extracted", "",
        }
        if value.lower() in bad_tokens:
            return FALLBACK

        # Strip leading/trailing punctuation noise
        value = re.sub(r'^[\s\-_:;,\.]+|[\s\-_:;,\.]+$', '', value)
        if not value:
            return FALLBACK

        # ── Field-specific validation ─────────────────────────────────────────
        if field_type == "title":
            # Titles should be reasonably long and contain at least one word char
            if len(value) < 5 or not re.search(r'\w', value):
                return FALLBACK
            # Collapse internal whitespace
            value = re.sub(r'\s+', ' ', value)

        elif field_type == "party":
            # Party names: reject single characters and pure-numeric strings
            if len(value) < 2 or re.fullmatch(r'[\d\s]+', value):
                return FALLBACK
            value = re.sub(r'\s+', ' ', value)
            # Strip stray quotes
            value = value.strip('"\'')

        elif field_type == "court":
            if len(value) < 4:
                return FALLBACK
            value = self._normalize_court_name(value)

        elif field_type == "bench":
            if len(value) < 3:
                return FALLBACK
            # Normalise each judge name in a comma-separated list
            parts = [self._normalize_judge_name(p) for p in value.split(",") if p.strip()]
            parts = [p for p in parts if len(p) >= 3]
            value = ", ".join(parts) if parts else FALLBACK

        elif field_type == "case_id":
            # Case IDs must contain at least one digit
            if not re.search(r'\d', value):
                return FALLBACK
            value = re.sub(r'\s+', ' ', value)

        # ── Final length guard ────────────────────────────────────────────────
        if len(value) > 500:
            value = value[:500].rstrip() + "…"

        return value if value else FALLBACK

    def _extract_from_image(self, content: bytes) -> str:
        try:
            return pytesseract.image_to_string(Image.open(io.BytesIO(content)))
        except: return ""

    def _normalize_court_name(self, val: str) -> str:
        """Standardizes naming conventions for prominent Indian Courts."""
        val = re.sub(r'\s+', ' ', val).strip()
        val = val.strip('.,;:- ')
        val_lower = val.lower()
        if "supreme court" in val_lower:
            return "Supreme Court of India"
        elif "karnataka high court" in val_lower or "high court of karnataka" in val_lower:
            return "High Court of Karnataka"
        elif "andhra pradesh high court" in val_lower or "high court of andhra pradesh" in val_lower:
            return "High Court of Andhra Pradesh"
        elif "allahabad high court" in val_lower or "high court of judicature at allahabad" in val_lower:
            return "Allahabad High Court"
        elif "delhi high court" in val_lower or "high court of delhi" in val_lower:
            return "Delhi High Court"
        return val

    def _normalize_judge_name(self, name: str) -> str:
        """Removes judicial prefixes and formats judge names cleanly."""
        name = re.sub(r'\s+', ' ', name).strip()
        prefix_pat = re.compile(
            r'^\s*(?:Hon\'?ble|Hon’ble|Honble|Hon|Justice|Mr\.?|Mrs\.?|Shri|Dr\.?)\b\s*',
            re.IGNORECASE
        )
        suffix_pat = re.compile(
            r'\s*,\s*(?:J\.?|C\.?J\.?|CJ\.?|Justice)\s*$|\s+\b(?:J\.?|C\.?J\.?|CJ\.?|Justice)\b\s*$',
            re.IGNORECASE
        )
        prev_name = ""
        while name != prev_name:
            prev_name = name
            name = prefix_pat.sub('', name).strip()
            name = suffix_pat.sub('', name).strip()
            name = name.strip('.,; -')
        return name

    def _extract_legal_outcome(self, text: str) -> str:
        """Extracts the final legal outcome using targeted regex and keyword analysis."""
        conclusion_text = text[-3000:] if len(text) > 3000 else text
        
        outcome_patterns = [
            (r'\b(?:Appeal|Petition|Application|Bail)\s+(?:is\s+)?allowed\b', "Allowed"),
            (r'\b(?:Appeal|Petition|Application|Bail)\s+(?:is\s+)?dismissed\b', "Dismissed"),
            (r'\b(?:Appeal|Petition|Application|Bail)\s+(?:is\s+)?rejected\b', "Rejected"),
            (r'\b(?:Bail|Relief)\s+(?:is\s+)?granted\b', "Granted"),
            (r'\b(?:Bail|Relief)\s+(?:is\s+)?refused\b', "Refused"),
            (r'\b(?:Conviction|Order)\s+(?:is\s+)?upheld\b', "Conviction Upheld"),
            (r'\b(?:Conviction|Order)\s+(?:is\s+)?set\s+aside\b', "Set Aside"),
            (r'\b(?:Accused|Petitioner)\s+(?:is\s+)?acquitted\b', "Acquitted"),
            (r'\b(?:Case|Matter)\s+(?:is\s+)?remanded\b', "Case Remanded"),
            (r'\b(?:Matter|Petition)\s+(?:is\s+)?disposed\s+of\b', "Matter Disposed"),
            (r'\b(?:Interim\s+relief|Stay)\s+(?:is\s+)?vacated\b', "Stay Vacated"),
            (r'\b(?:Cost|Penalty)\s+(?:is\s+)?imposed\b', "Penalty Imposed")
        ]

        for pattern, label in outcome_patterns:
            if re.search(pattern, conclusion_text, re.IGNORECASE):
                match = re.search(r'([A-Z][^.]*?' + pattern + r'[^.]*?\.)', conclusion_text, re.IGNORECASE)
                if match: return match.group(1).strip()
                return label

        order_keywords = ["ORDER", "CONCLUSION", "HELD", "PRONOUNCED"]
        for kw in order_keywords:
            if kw in conclusion_text.upper():
                parts = re.split(kw, conclusion_text, flags=re.IGNORECASE)
                if len(parts) > 1:
                    snippet = parts[-1][:200].strip()
                    if snippet: return snippet

        return "Outcome Pending Review"

    def _extract_dates_robustly(self, text: str) -> Dict[str, str]:
        """High-fidelity date extraction for filing, judgment, and hearing dates."""
        dates = {"filing_date": "Not Available", "judgment_date": "Not Available", "hearing_date": "Not Available"}
        full_date_pattern = r'(\b\d{1,2}(?:\s+|[-/])(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2})(?:\s+|[-/])\d{4}\b|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b)'
        
        judgment_contexts = [r'judgment\s+on\s+', r'dated\s+the\s+', r'decided\s+on\s+', r'dated\s+this\s+']
        for kw in judgment_contexts:
            match = re.search(kw + full_date_pattern, text, re.IGNORECASE)
            if match:
                dates["judgment_date"] = match.group(1).strip()
                break

        filing_contexts = [
            r'filing\s+date\s*', r'filed\s+on\s*', r'date\s+of\s+filing\s*', 
            r'institution\s+date\s*', r'date\s+of\s+institution\s*', 
            r'presented\s+on\s*', r'instituted\s+on\s*', 
            r'appeal\s+filed\s*'
        ]
        for kw in filing_contexts:
            match = re.search(kw + r'[:\-]?\s*' + full_date_pattern, text, re.IGNORECASE)
            if match:
                dates["filing_date"] = match.group(1).strip()
                break

        hearing_match = re.search(r'hearing\s+on\s*' + full_date_pattern, text, re.IGNORECASE)
        if hearing_match: dates["hearing_date"] = hearing_match.group(1).strip()

        for k, v in dates.items():
            if v and v != "Not Available":
                try:
                    parsed = dateparser.parse(
                        str(v), 
                        settings={
                            'STRICT_PARSING': True,
                            'REQUIRE_PARTS': ['day', 'month', 'year'],
                            'PREFER_DAY_OF_MONTH': 'first'
                        }
                    )
                    if parsed: dates[k] = parsed.strftime("%Y-%m-%d")
                    else: dates[k] = "Not Available"
                except: pass
                
        return dates

    async def summarize_cluster(self, summaries: List[str]) -> Dict[str, Any]:
        prompt = f"Summarize these legal cases into a theme: {summaries[:5]}. Return JSON with 'label' (short name), 'reason' (description), and 'legal_tags' (list of 3 strings)."
        try:
            res = self.llm.invoke(prompt)
            res_str = res.content if hasattr(res, 'content') else str(res)
            return json.loads(res_str)
        except: return {"label": "Semantic Cluster", "reason": "Cases grouped by legal similarity.", "legal_tags": ["Legal", "Matter"]}

intelligence_engine = IntelligenceEngine()
