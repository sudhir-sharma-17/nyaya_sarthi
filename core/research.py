import httpx
import json
import os
from typing import List, Dict, Any
from app.config import settings
from core.engine import engine_room

class LegalResearchEngine:
    """
    Handles retrieval of legal precedents and external knowledge.
    Integrates with ChromaDB and (optionally) external Legal APIs.
    """
    
    def __init__(self):
        self.indian_kanoon_base_url = "https://indiankanoon.org/api/"
        # In a real scenario, an API key would be required.
        self.api_key = os.getenv("INDIAN_KANOON_API_KEY", "")

    async def get_context(self, case_text: str) -> str:
        """
        Combines local vector search with external legal knowledge.
        """
        # 1. Local Vector Search (RAG)
        local_results = engine_room.search_similar(case_text[:1000], limit=3)
        
        context = "### Local Judicial Precedents (from Database):\n"
        if local_results and local_results.get("documents"):
            for i, doc in enumerate(local_results["documents"][0]):
                meta = local_results["metadatas"][0][i]
                context += f"- [{meta.get('case_title')}] {doc[:400]}...\n"
        else:
            context += "No direct local precedents found.\n"
            
        # 2. Simulated External Legal Knowledge (Indian Kanoon / eCourts)
        # In a real implementation, this would be an async HTTP call.
        context += "\n### Relevant Statutes & External Legal Knowledge:\n"
        context += self._get_simulated_external_knowledge(case_text)
        
        return context

    def _get_simulated_external_knowledge(self, text: str) -> str:
        """
        Heuristic-based legal knowledge retrieval (to be replaced by real API calls).
        """
        text = text.lower()
        knowledge = ""
        
        if "bail" in text:
            knowledge += "- Section 437/439 CrPC: Provisions for bail in non-bailable offences.\n"
            knowledge += "- State of Rajasthan v. Balchand (1977): 'Bail is the rule, Jail is the exception'.\n"
        
        if "domestic violence" in text:
            knowledge += "- Protection of Women from Domestic Violence Act, 2005 (PWDVA).\n"
            knowledge += "- Lalita Toppo v. State of Jharkhand (2018): Maintenance under PWDVA.\n"
            
        if "habeas corpus" in text:
            knowledge += "- Article 226/32 of the Constitution of India.\n"
            knowledge += "- ADM Jabalpur v. Shivkant Shukla (Overruled by KS Puttaswamy).\n"

        if not knowledge:
            knowledge = "- Generic legal principles under IPC, CrPC, and Indian Evidence Act apply.\n"
            
        return knowledge

    def get_similar_precedents(self, case_text: str, limit: int = 5, allowed_case_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves similar precedents from the vector database.
        If allowed_case_ids is provided, only those case IDs are searched (session isolation).
        """
        # If session filter is active, restrict ChromaDB query to only those IDs
        if allowed_case_ids and len(allowed_case_ids) > 0:
            try:
                results = engine_room.search_similar_filtered(
                    case_text[:1000],
                    limit=limit,
                    allowed_ids=allowed_case_ids
                )
            except Exception:
                results = engine_room.search_similar(case_text[:1000], limit=limit)
        else:
            results = engine_room.search_similar(case_text[:1000], limit=limit)
        
        precedents = []
        
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                doc_id = results["ids"][0][i]
                
                # Skip if not in allowed list (extra guard)
                if allowed_case_ids and doc_id not in allowed_case_ids:
                    continue
                
                # Try to parse stringified metadata values
                for k, v in meta.items():
                    if isinstance(v, str) and v.startswith(("[", "{")):
                        try:
                            meta[k] = json.loads(v)
                        except:
                            pass
                
                precedents.append({
                    "id": doc_id,
                    "title": meta.get('case_title', 'Unknown Case'),
                    "court": meta.get('court_name', 'Unknown Court'),
                    "date": meta.get('filing_date', 'Unknown Date'),
                    "similarity_score": results["distances"][0][i] if "distances" in results and results["distances"] else 0.0,
                    "summary": doc[:500] + "...",
                    "meta": meta
                })
        return precedents

    async def ask_legal_question(self, case_context: str, precedents: List[Dict[str, Any]], question: str) -> str:
        """
        Uses LLM to answer a legal question based on the case context and retrieved precedents.
        """
        from core.intelligence import intelligence_engine
        
        if not intelligence_engine.llm:
            return "Error: LLM engine is not available for Legal RAG."
            
        precedents_text = ""
        for p in precedents:
            precedents_text += f"\n- Case: {p['title']}\n  Summary: {p['summary']}\n"
            
        prompt = f"""
You are a highly experienced Indian Judicial AI Assistant.
You are helping a judge or a legal researcher understand a specific case and its relation to historical precedents.

### Context (Current Case):
{case_context[:1500]}

### Historical Precedents (from Database):
{precedents_text}

### User Question:
{question}

Based ON THE ABOVE CONTEXT AND PRECEDENTS ONLY, provide a clear, professional, and well-reasoned legal answer. 
Do not hallucinate citations. If the precedents don't cover the answer, state that explicitly but provide general legal principles under Indian law if applicable.

Return valid JSON strictly matching this format:
{{
  "answer": "Your detailed markdown-formatted answer here"
}}
"""
        try:
            response = intelligence_engine.llm.invoke(prompt)
            res_text = response.content if hasattr(response, 'content') else str(response)
            
            # Cleanup JSON
            res_text = res_text.strip()
            if "```json" in res_text: res_text = res_text.split("```json")[1].split("```")[0].strip()
            elif "```" in res_text: res_text = res_text.split("```")[1].split("```")[0].strip()
            
            start = res_text.find('{')
            end = res_text.rfind('}')
            if start != -1 and end != -1:
                answer_json = json.loads(res_text[start:end+1])
                return answer_json.get("answer", "Error: No answer generated.")
            return "Error parsing LLM response."
            
        except Exception as e:
            return f"Error analyzing question: {e}"

    async def analyze_case_query(self, case_model, query: str) -> str:
        """
        Analyzes a case-specific query using semantic intent mapping and fallback vector retrieval.
        Handles short queries and multilingual intents.
        """
        import re
        from core.intelligence import intelligence_engine
        
        # 1. Normalize Query
        normalized_query = re.sub(r'[^\w\s]', '', query.lower()).strip()
        words = normalized_query.split()
        
        # 2. Semantic Intent Mapping
        intents = {
            "bench": ["bench", "judge", "judges", "panel", "bench members", "judge name", "judge kaun hai", "ಯಾರು ಜಡ್ಜ್"],
            "author": ["author", "authoring judge", "written by"],
            "summary": ["summary", "summarize", "explain", "gist", "overview", "ಈ ಕೇಸ್ summary", "explain case"],
            "issue": ["issue", "legal issue", "problem", "dispute"],
            "facts": ["facts", "background", "story"],
            "outcome": ["outcome", "decision", "verdict", "result", "who won", "appeal", "फैसला क्या है", "outcome kya hai"],
            "statutes": ["sections", "acts", "laws", "statutes"],
            "citations": ["citations", "precedents", "references"],
            "timeline": ["date", "filing date", "hearing", "judgment date", "timeline"],
            "reasoning": ["reasoning", "why", "logic", "grounds", "court reasoning", "arguments", "why appeal dismissed"],
            "petitioner": ["petitioner", "appellant", "who sued"],
            "respondent": ["respondent", "defendant"],
            "court": ["court", "which court", "forum"]
        }
        
        mapped_intent = None
        # Exact/Partial match for short queries (<= 4 words)
        if len(words) <= 4:
            for intent, keywords in intents.items():
                if normalized_query in keywords or any(kw in normalized_query for kw in keywords):
                    mapped_intent = intent
                    break
        
        context_text = ""
        import json
        try:
            raw_data = json.loads(case_model.raw_content) if case_model.raw_content else {}
        except:
            raw_data = {}
            
        full_text = raw_data.get("full_text", "")
        
        # 3. Intent Execution - Return Metadata Directly
        if mapped_intent:
            if mapped_intent == "bench":
                return {"answer": f"Bench/Judges: {case_model.bench or raw_data.get('bench', 'Not available')}", "evidence": []}
            elif mapped_intent == "author":
                return {"answer": f"Authoring Judge: {raw_data.get('author_judge', 'Not available')}", "evidence": []}
            elif mapped_intent == "petitioner":
                return {"answer": f"Petitioner: {raw_data.get('petitioner', 'Not available')}", "evidence": []}
            elif mapped_intent == "respondent":
                return {"answer": f"Respondent: {raw_data.get('respondent', 'Not available')}", "evidence": []}
            elif mapped_intent == "court":
                return {"answer": f"Court: {case_model.court_name or raw_data.get('court_name', 'Not available')}", "evidence": []}
            elif mapped_intent == "outcome":
                return {"answer": f"Outcome: {raw_data.get('legal_outcome', 'Not available')}", "evidence": []}
            elif mapped_intent == "timeline":
                return {"answer": f"Filing Date: {case_model.filing_date}, Judgment Date: {case_model.judgment_date}", "evidence": []}
            elif mapped_intent == "statutes":
                return {"answer": f"Statutes & Sections: {case_model.extracted_statutes}", "evidence": []}
            elif mapped_intent == "citations":
                return {"answer": f"Citations: {case_model.citations}", "evidence": []}
            elif mapped_intent == "issue":
                return {"answer": f"Legal Issue: {case_model.legal_issue}", "evidence": []}
            # For reasoning, facts, summary, we still want to use LLM to summarize/explain.
            elif mapped_intent == "summary":
                context_text = f"Case Summary: {case_model.summary}"
            elif mapped_intent == "facts":
                context_text = f"Facts: {raw_data.get('facts', case_model.summary)}"
            elif mapped_intent == "reasoning":
                context_text = f"Reasoning: {case_model.reasoning}"
        
        evidence_list = []
        # 4. Fallback Semantic Vector Retrieval
        if not context_text:
            if not full_text:
                full_text = f"Title: {case_model.title}\nSummary: {case_model.summary}\nIssue: {case_model.legal_issue}"
            
            top_chunks = engine_room.semantic_search_chunks(query, full_text, top_k=3)
            evidence_list = top_chunks
            context_text = "\n\n".join(top_chunks)
            if not context_text:
                context_text = "No relevant context found in the document chunks."
        else:
            evidence_list = [context_text]

        # 5. LLM Response Generation
        if not intelligence_engine.llm:
            return {"answer": "Error: LLM engine is not available.", "evidence": []}
            
        prompt = f"""
You are a highly experienced Indian Judicial AI Assistant.
Answer the user's question about the following case based ONLY on the provided Context.
Keep the answer concise.
If the answer is not found in the Context, output exactly: "Information not explicitly available in extracted judgment."
Do not hallucinate any citations, facts, or outcomes.

### Context from Case:
{context_text}

### User Question:
{query}

Return valid JSON strictly matching this format:
{{
  "answer": "Your concise answer here"
}}
"""
        try:
            response = intelligence_engine.llm.invoke(prompt)
            res_text = response.content if hasattr(response, 'content') else str(response)
            
            res_text = res_text.strip()
            if "```json" in res_text: res_text = res_text.split("```json")[1].split("```")[0].strip()
            elif "```" in res_text: res_text = res_text.split("```")[1].split("```")[0].strip()
            
            start = res_text.find('{')
            end = res_text.rfind('}')
            if start != -1 and end != -1:
                answer_json = json.loads(res_text[start:end+1])
                return {"answer": answer_json.get("answer", "Information not explicitly available in extracted judgment."), "evidence": evidence_list}
            return {"answer": "Information not explicitly available in extracted judgment.", "evidence": evidence_list}
            
        except Exception as e:
            return {"answer": f"Error analyzing question: {e}", "evidence": []}

legal_research = LegalResearchEngine()
