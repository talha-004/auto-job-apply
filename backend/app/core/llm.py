import json
import re
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.logger import logger


class BaseLLMClient(ABC):
    """Abstract Base Class for LLM Providers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Check if provider service/API is reachable."""
        pass

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate free-form text from prompt."""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate parsed JSON dictionary from prompt."""
        pass

    def extract_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from model output, handling potential markdown blocks or syntax issues."""
        if not text:
            return {}

        # 1. Direct json loads
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 2. Extract from markdown code block ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. Extract bracket to bracket { ... }
        match_bracket = re.search(r"\{[\s\S]*\}", text)
        if match_bracket:
            try:
                return json.loads(match_bracket.group(0).strip())
            except json.JSONDecodeError:
                pass

        logger.warning(f"[{self.name}] Could not parse JSON from output: {text[:200]}...")
        return {}

    # Backward compatibility alias
    _extract_json = extract_json



class OllamaLLMClient(BaseLLMClient):
    """Local Ollama LLM provider."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        timeout_seconds: int = settings.OLLAMA_TIMEOUT_SECONDS
    ):
        super().__init__(name="Ollama")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = httpx.Timeout(float(timeout_seconds), connect=3.0)

    async def check_health(self) -> Dict[str, Any]:
        """Check if Ollama server is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    model_available = any(self.model in m or m.startswith(self.model.split(":")[0]) for m in models)
                    return {
                        "provider": self.name,
                        "online": True,
                        "models": models,
                        "model_ready": model_available,
                        "configured_model": self.model
                    }
        except Exception as e:
            return {
                "provider": self.name,
                "online": False,
                "error": str(e),
                "model_ready": False,
                "configured_model": self.model
            }
        return {"provider": self.name, "online": False, "model_ready": False, "configured_model": self.model}

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text using Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "You are an intelligent assistant for automated job applications.",
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9}
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code == 200:
                    return response.json().get("response", "").strip()
                logger.error(f"[Ollama] Error {response.status_code}: {response.text}")
                return ""
        except Exception as e:
            logger.error(f"[Ollama] Generation failed: {e}")
            return ""

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Send a prompt to Ollama requesting strict JSON output."""
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
            "options": {"temperature": 0.1, "top_p": 0.9}
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code != 200:
                    logger.error(f"[Ollama] Error {response.status_code}: {response.text}")
                    return {}

                raw_response = response.json().get("response", "").strip()
                return self.extract_json(raw_response)
        except httpx.ConnectError:
            logger.error(f"[Ollama] Cannot connect to {self.base_url}. Make sure 'ollama serve' is running.")
            return {}
        except Exception as e:
            logger.error(f"[Ollama] Error calling LLM: {str(e)}")
            return {}


class GeminiLLMClient(BaseLLMClient):
    """Google Gemini LLM provider via REST API."""

    def __init__(
        self,
        api_key: Optional[str] = settings.GEMINI_API_KEY,
        model: str = settings.GEMINI_MODEL or "gemini-1.5-flash",
        timeout_seconds: int = 60
    ):
        super().__init__(name="Gemini")
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(float(timeout_seconds), connect=10.0)

    async def check_health(self) -> Dict[str, Any]:
        """Check if Gemini API key is configured."""
        if not self.api_key:
            return {
                "provider": self.name,
                "online": False,
                "configured": False,
                "reason": "GEMINI_API_KEY is not configured",
                "configured_model": self.model
            }
        return {
            "provider": self.name,
            "online": True,
            "configured": True,
            "configured_model": self.model
        }

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text using Gemini API."""
        if not self.api_key:
            logger.warning("[Gemini] API key missing; skipping call.")
            return ""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow all instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        body = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2, "topP": 0.9}
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=body)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                logger.error(f"[Gemini] Error {res.status_code}: {res.text}")
                return ""
        except Exception as e:
            logger.error(f"[Gemini] API error: {e}")
            return ""

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate JSON using Gemini API."""
        full_sys = (system_prompt or "") + "\nRespond with valid JSON only. Do not include markdown ticks."
        text = await self.generate_text(prompt, system_prompt=full_sys)
        return self.extract_json(text)


class OpenAICompatibleLLMClient(BaseLLMClient):
    """OpenAI-compatible LLM provider (supports DeepSeek, Groq, local vLLM, etc.)."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
        timeout_seconds: int = 60
    ):
        super().__init__(name=name)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(float(timeout_seconds), connect=10.0)

    async def check_health(self) -> Dict[str, Any]:
        """Check if provider has API key configured."""
        if not self.api_key:
            return {
                "provider": self.name,
                "online": False,
                "configured": False,
                "reason": f"{self.name} API key not configured",
                "configured_model": self.model
            }
        return {
            "provider": self.name,
            "online": True,
            "configured": True,
            "configured_model": self.model
        }

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text via /chat/completions."""
        if not self.api_key:
            logger.warning(f"[{self.name}] API key missing; skipping call.")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                logger.error(f"[{self.name}] Error {res.status_code}: {res.text}")
                return ""
        except Exception as e:
            logger.error(f"[{self.name}] Request failed: {e}")
            return ""

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate JSON via /chat/completions."""
        full_sys = (system_prompt or "") + "\nRespond with valid JSON only."
        text = await self.generate_text(prompt, system_prompt=full_sys)
        return self.extract_json(text)


class UnifiedLLMClient(BaseLLMClient):
    """
    Unified LLM Client providing automated provider selection and resilient fallback routing:
    Primary Choice -> Secondary Choice -> Graceful Degraded Heuristics.
    """

    def __init__(self):
        super().__init__(name="UnifiedLLM")
        self.ollama = OllamaLLMClient()
        self.gemini = GeminiLLMClient()
        self.deepseek = OpenAICompatibleLLMClient(
            name="DeepSeek",
            base_url="https://api.deepseek.com/v1",
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.DEEPSEEK_MODEL
        )
        self.groq = OpenAICompatibleLLMClient(
            name="Groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL
        )

    def _get_provider_chain(self) -> List[BaseLLMClient]:
        """Determine priority ordered list of active LLM clients."""
        primary_name = (settings.PRIMARY_LLM_PROVIDER or "ollama").lower()
        mapping = {
            "ollama": self.ollama,
            "gemini": self.gemini,
            "deepseek": self.deepseek,
            "groq": self.groq
        }

        chain: List[BaseLLMClient] = []
        # Add primary if recognized
        if primary_name in mapping:
            chain.append(mapping[primary_name])

        # Add remaining available providers as fallback
        for key, client in mapping.items():
            if client not in chain:
                chain.append(client)

        return chain

    async def check_health(self) -> Dict[str, Any]:
        """Check status of all configured providers."""
        providers_status = {
            "ollama": await self.ollama.check_health(),
            "gemini": await self.gemini.check_health(),
            "deepseek": await self.deepseek.check_health(),
            "groq": await self.groq.check_health(),
        }
        active_provider = settings.PRIMARY_LLM_PROVIDER
        return {
            "unified_ready": any(p.get("online") or p.get("configured") for p in providers_status.values()),
            "primary_provider": active_provider,
            "providers": providers_status
        }

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Execute text generation with cascading provider fallback."""
        for client in self._get_provider_chain():
            try:
                res = await client.generate_text(prompt, system_prompt=system_prompt)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Provider {client.name} failed: {e}. Trying fallback...")
        return ""

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Execute JSON generation with cascading provider fallback."""
        for client in self._get_provider_chain():
            try:
                res = await client.generate_json(prompt, system_prompt=system_prompt)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Provider {client.name} JSON failed: {e}. Trying fallback...")
        return {}

    # Backward compatibility with existing methods in OllamaLLMClient
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
        Given candidate profile and detected form input fields, intelligently determine the exact value to fill.
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
If free-form, provide a concise professional 1-2 sentence response grounded strictly in the candidate profile without fabricating facts.
Return JSON: {{"answer": "your answer here"}}
"""
        res = await self.generate_json(prompt)
        return str(res.get("answer", ""))


# Export default unified client instance
llm_client = UnifiedLLMClient()
