import json
import re
import httpx
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.logger import logger

class OllamaLLMClient:
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = httpx.Timeout(float(settings.OLLAMA_TIMEOUT_SECONDS), connect=10.0)

    async def check_health(self) -> Dict[str, Any]:
        """Check if Ollama server is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    model_available = any(self.model in m or m.startswith(self.model.split(":")[0]) for m in models)
                    return {
                        "online": True,
                        "models": models,
                        "model_ready": model_available,
                        "configured_model": self.model
                    }
        except Exception as e:
            return {
                "online": False,
                "error": str(e),
                "model_ready": False,
                "configured_model": self.model
            }
        return {"online": False, "model_ready": False, "configured_model": self.model}

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Send a prompt to Ollama requesting strict JSON output with fallback cleanup."""
        system_instruction = (
            system_prompt or 
            "You are an expert AI assistant specialized in parsing candidate resumes and filling job application forms accurately. "
            "Always respond strictly with valid JSON without conversational preamble or markdown code blocks unless requested."
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_instruction,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code != 200:
                    logger.error(f"Ollama error {response.status_code}: {response.text}")
                    return {}

                result = response.json()
                raw_response = result.get("response", "").strip()
                return self._extract_json(raw_response)
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.base_url}. Make sure 'ollama serve' is running.")
            return {}
        except Exception as e:
            logger.error(f"Error calling Ollama LLM: {str(e)}")
            return {}

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from model output, handling potential markdown blocks or syntax issues."""
        if not text:
            return {}
        
        # Try direct json loads first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try extracting bracket to bracket { ... }
        match_bracket = re.search(r"\{[\s\S]*\}", text)
        if match_bracket:
            try:
                return json.loads(match_bracket.group(0).strip())
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse JSON from output: {text[:200]}...")
        return {}

    async def parse_resume_text(self, resume_text: str) -> Dict[str, Any]:
        """Convert raw resume text into structured ResumeProfile JSON schema."""
        prompt = f"""
You are an expert resume parser. Analyze the following candidate resume text and extract all details into a clean JSON structure matching this exact schema:

{{
  "full_name": "Full Name",
  "email": "Email address",
  "phone": "Phone number with country code if available",
  "location": "City, State / Country",
  "linkedin_url": "LinkedIn profile link or empty string",
  "github_url": "GitHub link or empty string",
  "portfolio_url": "Personal portfolio link or empty string",
  "years_of_experience": 3.5,
  "summary": "2-3 sentence professional summary",
  "skills": ["Skill 1", "Skill 2", "Skill 3"],
  "work_experience": [
    {{
      "company": "Company Name",
      "title": "Job Title",
      "start_date": "Month Year or Year",
      "end_date": "Month Year or Present",
      "location": "City / Remote",
      "description": "Key achievements and responsibilities"
    }}
  ],
  "education": [
    {{
      "institution": "University / College Name",
      "degree": "Degree (e.g. Bachelor of Science)",
      "field": "Computer Science or related",
      "graduation_year": "2023",
      "grade_or_gpa": "Grade or GPA if mentioned"
    }}
  ],
  "certifications": ["Certification 1", "Certification 2"],
  "languages": ["English", "Hindi"]
}}

Resume text to analyze:
\"\"\"
{resume_text}
\"\"\"

Return ONLY the JSON object.
"""
        return await self.generate_json(prompt)

    async def map_form_fields(
        self,
        candidate_profile: Dict[str, Any],
        detected_fields: List[Dict[str, Any]],
        job_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Given the candidate profile and a list of detected form input fields (id, name, label, type, options, placeholder),
        use the LLM to intelligently determine the exact value to enter into each field.
        """
        job_info = f"Job Title: {job_context.get('title', '')}, Company: {job_context.get('company', '')}" if job_context else ""

        prompt = f"""
You are an intelligent auto-fill agent completing a job application form.
{job_info}

Here is the candidate's complete profile:
{json.dumps(candidate_profile, indent=2)}

Here are the detected input fields on the current page:
{json.dumps(detected_fields, indent=2)}

TASK:
For each field in the detected input fields list, determine the best value to fill or select.
Rules:
1. For text/email/tel/number inputs: Provide the exact string or number matching candidate profile.
2. For select/dropdown or radio groups: Choose the EXACT matching option value from the provided 'options' list. If none matches closely, choose the most sensible option (e.g. 'Yes' for work authorization, 'No' for sponsorship).
3. For checkboxes: return boolean true or false.
4. For questions like 'How many years of experience with X?': estimate based on candidate skills and work history (numeric string, e.g. "3").
5. For open-ended questions like 'Why do you want to work here?' or 'Cover letter': generate a concise, professional 2-3 sentence response matching the candidate's skills.

Return a JSON object where each key is the field's "id" (or "name" if id is not available) and the value is the filled value.
Example format:
{{
  "first_name_input": "Syed",
  "last_name_input": "Ahmed",
  "years_exp_select": "3-5 years",
  "authorized_to_work_radio": "Yes",
  "expected_salary": "Negotiable"
}}
"""
        return await self.generate_json(prompt)

    async def answer_screening_question(
        self,
        candidate_profile: Dict[str, Any],
        question_text: str,
        options: Optional[List[str]] = None
    ) -> str:
        """Answer a single screening question using candidate profile context."""
        options_text = f"Available options: {', '.join(options)}" if options else "Free-form answer."
        prompt = f"""
Candidate profile:
{json.dumps(candidate_profile, indent=2)}

Job Application Screening Question:
\"{question_text}\"
{options_text}

Provide the best accurate answer for this candidate.
If options are given, return ONLY the exact option string.
If free-form, provide a concise professional 1-2 sentence response.
Return JSON: {{"answer": "your answer here"}}
"""
        res = await self.generate_json(prompt)
        return str(res.get("answer", ""))

llm_client = OllamaLLMClient()
