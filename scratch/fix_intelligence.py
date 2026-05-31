import os

file_path = "/Users/prajwalnaik/Desktop/court_ai_judiciary/core/intelligence.py"

replacement = """class IntelligenceEngine:
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
        \"\"\"High-fidelity multi-stage extraction pipeline.\"\"\"
        text, method = self._robust_extract_text(file_content, file_name)
        text = self._clean_text(text)
        
        if len(text.strip()) < 50:
            extracted = self._fallback_regex_extraction(text)
            return self._ensure_metadata_integrity(extracted, text)

        # Smart Truncation: Focus on first 3 pages (approx 9000 chars) and last 2 pages (approx 6000 chars)
        llm_input = text[:9000]
        if len(text) > 10000:
            llm_input += "\\n\\n[... DOCUMENT MID-SECTION OMITTED ...]\\n\\n[... FINAL CHAPTERS / CONCLUSION ...]\\n\\n" + text[-6000:]
        
        prompt = PromptTemplate(
            template=\"\"\"
            You are a senior Indian Judicial Analyst. Perform a deep-dive analysis on the provided case text.
            
            CRITICAL INSTRUCTIONS:
            1. SUMMARY: Generate a unique, document-specific summary including:
               - Key Facts
               - The Dispute
               - Core Legal Issue
               - Court's Decision
            2. LEGAL ISSUE: Extract exactly ONE concise sentence (e.g. 'Validity of tax transfer order without notice').
            3. RELIEF REQUESTED: Identify what the petitioner/appellant specifically prayed for (e.g. 'Quashing of Order', 'Bail', 'Acquittal').
            4. FINAL DECISION: Analyze the ENDING paragraphs. Detect the final legal outcome (e.g. 'Appeal Allowed', 'Conviction Upheld').
            5. PRIORITY: Generate a unique reasoning based on the case's nature (Criminal/Bail/Humanitarian = High, Tax/Civil = Low/Medium).
            
            Return valid JSON only:
            {{
             "case_title": "Short descriptive title",
             "case_number_extracted": "e.g. WP 123/2023",
             "petitioner": "Full Name",
             "respondent": "Full Name",
             "court_name": "Full Name of Court",
             "bench": "Judges",
             "case_type_inferred": "e.g. Criminal, Tax, Civil",
             "filing_date": "YYYY-MM-DD",
             "judgment_date": "YYYY-MM-DD",
             "relief_sought": "Detected prayer/relief",
             "core_legal_issue": "ONE concise sentence",
             "legal_outcome": "Final result of the case",
             "acts": ["Act 1"],
             "sections": ["Section X"],
             "citations": ["Citation 1"],
             "summary": "Detailed 4-6 line case-specific intelligence summary (Facts, Dispute, Issue, Decision)",
             "urgency_score": "Score 0-100",
             "priority_reasoning_summary": "Unique reasoning for this specific case"
            }}

            ### DOCUMENT EXTRACT (Start + Conclusion):
            {text}
            \"\"\",
            input_variables=["text"]
        )

        extracted = None
        if self.llm:
            try:
                response = self.llm.invoke(prompt.format(text=llm_input))
                res_text = response.content if hasattr(response, 'content') else str(response)
                
                # Cleanup JSON
                res_text = res_text.strip()
                if \"```json\" in res_text: res_text = res_text.split(\"```json\")[1].split(\"```\")[0].strip()
                elif \"```\" in res_text: res_text = res_text.split(\"```\")[1].split(\"```\")[0].strip()
                
                start = res_text.find('{')
                end = res_text.rfind('}')
                if start != -1 and end != -1:
                    extracted = json.loads(res_text[start:end+1])
            except Exception as e:
                print(f"LLM Extraction failed: {e}")

        if not extracted:
            extracted = self._fallback_regex_extraction(text)

        # Filename fallback for title
        if not extracted.get(\"case_title\") or \"available\" in str(extracted.get(\"case_title\")).lower():
            extracted[\"case_title\"] = file_name.replace(\".pdf\", \"\").replace(\"_\", \" \").title()

        extracted.update({
            \"extraction_method\": method,
            \"extracted_length\": len(text),
            \"full_text\": text
        })

        return self._ensure_metadata_integrity(extracted, text)

    """

with open(file_path, "r") as f:
    content = f.read()

class_start = content.find("class IntelligenceEngine:")
next_method = content.find("def _extract_dates_robustly")

if class_start != -1 and next_method != -1:
    new_content = content[:class_start] + replacement + content[next_method:]
    with open(file_path, "w") as f:
        f.write(new_content)
    print("Successfully updated intelligence.py")
else:
    print(f"Markers not found: class_start={class_start}, next_method={next_method}")
