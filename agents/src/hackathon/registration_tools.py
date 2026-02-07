"""
Hackathon Registration Tools

Playwright-based browser automation to:
1. Detect registration form fields on a hackathon page
2. Auto-fill user profile data into the form
3. Submit the registration

Supports Luma (lu.ma), Devpost, Eventbrite, and generic HTML forms.
"""

import os
import json
import asyncio
import logging
import re
from typing import Any

from pydantic import Field

from ..shared.tool_base import BaseTool

logger = logging.getLogger(__name__)

OPENAI_MODEL = "gpt-4o-mini"


# ─── User Profile ────────────────────────────────────────────

DEFAULT_PROFILE_FIELDS = [
    "full_name", "email", "phone", "github_url", "linkedin_url",
    "portfolio_url", "skills", "experience_level", "team_name",
    "dietary_restrictions", "tshirt_size", "country", "city",
    "university", "graduation_year", "resume_url", "bio",
]


class GetUserProfileTool(BaseTool):
    """
    Retrieve or build the user's profile for hackathon registration.
    """

    name: str = "get_user_profile"
    description: str = """
    Get the user's profile information needed for hackathon registration.
    Returns a JSON object with fields like full_name, email, phone,
    github_url, linkedin_url, skills, experience_level, etc.

    If a stored profile exists it is returned directly.
    Otherwise returns the profile with whatever fields are available.

    Call this BEFORE attempting registration to know what info you have.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user ID to look up (default: 'default')",
            },
        },
        "required": [],
    }

    async def execute(self, user_id: str = "default") -> str:
        """Return stored user profile or empty template."""
        profile_path = os.path.join(
            os.path.dirname(__file__), ".profiles", f"{user_id}.json"
        )
        if os.path.exists(profile_path):
            with open(profile_path) as f:
                profile = json.load(f)
            return json.dumps({"success": True, "profile": profile}, indent=2)

        # Return empty template so the LLM knows what to ask for
        template = {k: "" for k in DEFAULT_PROFILE_FIELDS}
        return json.dumps({
            "success": True,
            "profile": template,
            "note": "Profile not found — please collect info from the user.",
        }, indent=2)


class SaveUserProfileTool(BaseTool):
    """
    Save / update the user's registration profile.
    """

    name: str = "save_user_profile"
    description: str = """
    Save the user's profile information for future hackathon registrations.
    Pass individual fields to update; existing fields are preserved.

    Example: save_user_profile(full_name="Alice", email="alice@dev.io", skills="Python, Solidity")
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user ID (default: 'default')",
            },
            "full_name": {"type": "string", "description": "Full legal name"},
            "email": {"type": "string", "description": "Email address"},
            "phone": {"type": "string", "description": "Phone number"},
            "github_url": {"type": "string", "description": "GitHub profile URL"},
            "linkedin_url": {"type": "string", "description": "LinkedIn profile URL"},
            "portfolio_url": {"type": "string", "description": "Portfolio / personal website"},
            "skills": {"type": "string", "description": "Comma-separated skills"},
            "experience_level": {
                "type": "string",
                "description": "beginner / intermediate / advanced / professional",
            },
            "team_name": {"type": "string", "description": "Team name if applicable"},
            "dietary_restrictions": {"type": "string", "description": "Dietary needs"},
            "tshirt_size": {"type": "string", "description": "T-shirt size (S/M/L/XL)"},
            "country": {"type": "string", "description": "Country of residence"},
            "city": {"type": "string", "description": "City of residence"},
            "university": {"type": "string", "description": "University / school name"},
            "graduation_year": {"type": "string", "description": "Expected graduation year"},
            "bio": {"type": "string", "description": "Short bio (1-2 sentences)"},
        },
        "required": [],
    }

    async def execute(self, user_id: str = "default", **kwargs: Any) -> str:
        """Merge and persist profile data."""
        profiles_dir = os.path.join(os.path.dirname(__file__), ".profiles")
        os.makedirs(profiles_dir, exist_ok=True)

        profile_path = os.path.join(profiles_dir, f"{user_id}.json")

        # Load existing
        existing = {}
        if os.path.exists(profile_path):
            with open(profile_path) as f:
                existing = json.load(f)

        # Merge — only overwrite non-empty values
        for key, val in kwargs.items():
            if val and key in DEFAULT_PROFILE_FIELDS:
                existing[key] = val

        with open(profile_path, "w") as f:
            json.dump(existing, f, indent=2)

        filled = [k for k, v in existing.items() if v]
        return json.dumps({
            "success": True,
            "saved_fields": filled,
            "profile": existing,
        }, indent=2)


# ─── Form Detection & Registration ───────────────────────────

class DetectRegistrationFormTool(BaseTool):
    """
    Navigate to a hackathon page and detect registration form fields.
    Uses Playwright headless browser.
    """

    name: str = "detect_registration_form"
    description: str = """
    Open a hackathon registration page in a headless browser and detect
    all form fields (inputs, selects, textareas, checkboxes, radio buttons).

    Returns a JSON list of detected fields with their type, name, label,
    placeholder, and whether they are required.

    Use this BEFORE auto_fill_and_register to understand what the form needs.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The hackathon registration page URL",
            },
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> str:
        """Detect form fields on a registration page."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return json.dumps({
                "success": False,
                "error": "Playwright not installed. Run: pip install playwright && python -m playwright install chromium",
            })

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=30_000)
                await page.wait_for_timeout(2000)  # let JS render

                # Click any "Register" / "Sign Up" / "RSVP" button first
                for btn_text in ["Register", "Sign Up", "RSVP", "Apply", "Join", "Attend"]:
                    try:
                        btn = page.get_by_role("button", name=re.compile(btn_text, re.I)).first
                        if await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
                    try:
                        link = page.get_by_role("link", name=re.compile(btn_text, re.I)).first
                        if await link.is_visible():
                            await link.click()
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue

                # Extract all form fields
                fields = await page.evaluate("""() => {
                    const fields = [];
                    const inputs = document.querySelectorAll(
                        'input, select, textarea, [role="combobox"], [role="listbox"]'
                    );

                    inputs.forEach(el => {
                        // Skip hidden / honeypot fields
                        if (el.type === 'hidden' || el.offsetParent === null) return;

                        // Find label
                        let label = '';
                        if (el.id) {
                            const lbl = document.querySelector(`label[for="${el.id}"]`);
                            if (lbl) label = lbl.textContent.trim();
                        }
                        if (!label && el.closest('label')) {
                            label = el.closest('label').textContent.trim();
                        }
                        if (!label) {
                            // Check preceding sibling or parent text
                            const prev = el.previousElementSibling;
                            if (prev) label = prev.textContent.trim().slice(0, 100);
                        }
                        if (!label) label = el.getAttribute('aria-label') || '';

                        // Get options for selects
                        let options = [];
                        if (el.tagName === 'SELECT') {
                            options = Array.from(el.options).map(o => ({
                                value: o.value, text: o.textContent.trim()
                            })).filter(o => o.value);
                        }

                        fields.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || el.tagName.toLowerCase(),
                            name: el.name || el.id || '',
                            id: el.id || '',
                            label: label.slice(0, 200),
                            placeholder: (el.placeholder || '').slice(0, 200),
                            required: el.required || el.getAttribute('aria-required') === 'true',
                            value: el.value || '',
                            options: options,
                        });
                    });

                    return fields;
                }""")

                # Also grab the page title & current URL (may have redirected)
                title = await page.title()
                current_url = page.url

                await browser.close()

            return json.dumps({
                "success": True,
                "url": current_url,
                "page_title": title,
                "field_count": len(fields),
                "fields": fields,
            }, indent=2)

        except Exception as e:
            logger.error("Form detection failed: %s", e)
            return json.dumps({"success": False, "error": str(e)})


class AutoFillAndRegisterTool(BaseTool):
    """
    Auto-fill a hackathon registration form and submit it using Playwright.
    """

    name: str = "auto_fill_and_register"
    description: str = """
    Open the hackathon registration page, auto-fill all form fields
    using the provided user profile data, and submit the form.

    IMPORTANT: Call detect_registration_form first to know the fields,
    then call get_user_profile to have the data, then call this tool.

    Set dry_run=true to fill the form without submitting (preview mode).

    Returns a screenshot path and confirmation details.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The hackathon registration page URL",
            },
            "profile_json": {
                "type": "string",
                "description": "JSON string of user profile data to fill in",
            },
            "field_mapping_json": {
                "type": "string",
                "description": (
                    "Optional JSON string mapping form field names/ids to profile "
                    "keys, e.g. '{\"first-name\": \"full_name\", \"email-input\": \"email\"}'. "
                    "If not provided, the tool uses AI to auto-match fields."
                ),
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, fill the form but do NOT click submit (default: true for safety)",
            },
        },
        "required": ["url", "profile_json"],
    }

    async def execute(
        self,
        url: str,
        profile_json: str,
        field_mapping_json: str | None = None,
        dry_run: bool = True,
    ) -> str:
        """Fill and optionally submit a registration form."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return json.dumps({
                "success": False,
                "error": "Playwright not installed. Run: pip install playwright && python -m playwright install chromium",
            })

        try:
            profile = json.loads(profile_json)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid profile JSON"})

        field_mapping = {}
        if field_mapping_json:
            try:
                field_mapping = json.loads(field_mapping_json)
            except json.JSONDecodeError:
                pass

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=30_000)
                await page.wait_for_timeout(2000)

                # Click Register / RSVP button if present
                for btn_text in ["Register", "Sign Up", "RSVP", "Apply", "Join", "Attend"]:
                    try:
                        btn = page.get_by_role("button", name=re.compile(btn_text, re.I)).first
                        if await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
                    try:
                        link = page.get_by_role("link", name=re.compile(btn_text, re.I)).first
                        if await link.is_visible():
                            await link.click()
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue

                # If no explicit mapping, use AI to create one
                if not field_mapping:
                    field_mapping = await self._ai_field_mapping(page, profile)

                # Fill fields
                filled_fields = []
                for form_field, profile_key in field_mapping.items():
                    value = profile.get(profile_key, "")
                    if not value:
                        continue

                    try:
                        # Try by name, id, or label
                        selector = None
                        for sel in [
                            f"input[name='{form_field}']",
                            f"textarea[name='{form_field}']",
                            f"select[name='{form_field}']",
                            f"#{form_field}",
                            f"input[id='{form_field}']",
                            f"textarea[id='{form_field}']",
                        ]:
                            try:
                                el = page.locator(sel).first
                                if await el.is_visible(timeout=500):
                                    selector = sel
                                    break
                            except Exception:
                                continue

                        if not selector:
                            # Try by label text
                            try:
                                el = page.get_by_label(re.compile(form_field, re.I)).first
                                if await el.is_visible(timeout=500):
                                    await el.fill(str(value))
                                    filled_fields.append({"field": form_field, "value": str(value)[:50]})
                                    continue
                            except Exception:
                                pass
                            continue

                        el = page.locator(selector).first
                        tag = await el.evaluate("e => e.tagName.toLowerCase()")

                        if tag == "select":
                            await el.select_option(label=str(value))
                        elif tag in ("input", "textarea"):
                            input_type = await el.get_attribute("type") or "text"
                            if input_type == "checkbox":
                                if str(value).lower() in ("true", "yes", "1"):
                                    await el.check()
                            elif input_type == "radio":
                                await el.check()
                            else:
                                await el.fill(str(value))
                        else:
                            await el.fill(str(value))

                        filled_fields.append({"field": form_field, "value": str(value)[:50]})

                    except Exception as e:
                        logger.warning("Could not fill field %s: %s", form_field, e)

                # Take screenshot
                screenshots_dir = os.path.join(os.path.dirname(__file__), ".screenshots")
                os.makedirs(screenshots_dir, exist_ok=True)
                screenshot_path = os.path.join(
                    screenshots_dir,
                    f"registration_{hash(url) % 10000}.png",
                )
                await page.screenshot(path=screenshot_path, full_page=True)

                # Submit if not dry run
                submitted = False
                if not dry_run:
                    for btn_text in ["Submit", "Register", "Sign Up", "Complete", "Confirm", "RSVP"]:
                        try:
                            submit_btn = page.get_by_role("button", name=re.compile(btn_text, re.I)).first
                            if await submit_btn.is_visible():
                                await submit_btn.click()
                                await page.wait_for_timeout(3000)
                                submitted = True
                                # Take post-submit screenshot
                                await page.screenshot(
                                    path=screenshot_path.replace(".png", "_submitted.png"),
                                    full_page=True,
                                )
                                break
                        except Exception:
                            continue

                final_url = page.url
                final_title = await page.title()
                await browser.close()

            return json.dumps({
                "success": True,
                "dry_run": dry_run,
                "submitted": submitted,
                "url": final_url,
                "page_title": final_title,
                "fields_filled": len(filled_fields),
                "filled_details": filled_fields,
                "screenshot": screenshot_path,
                "message": (
                    "Form filled and submitted successfully!"
                    if submitted
                    else f"Form filled ({len(filled_fields)} fields). "
                    + ("Dry run — not submitted." if dry_run else "Could not find submit button.")
                ),
            }, indent=2)

        except Exception as e:
            logger.error("Auto-fill failed: %s", e)
            return json.dumps({"success": False, "error": str(e)})

    async def _ai_field_mapping(self, page, profile: dict) -> dict:
        """Use OpenAI to match form fields to profile keys."""
        from openai import AsyncOpenAI

        # Extract visible form fields
        fields_info = await page.evaluate("""() => {
            const fields = [];
            document.querySelectorAll('input, select, textarea').forEach(el => {
                if (el.type === 'hidden' || el.offsetParent === null) return;
                let label = '';
                if (el.id) {
                    const lbl = document.querySelector(`label[for="${el.id}"]`);
                    if (lbl) label = lbl.textContent.trim();
                }
                if (!label && el.closest('label'))
                    label = el.closest('label').textContent.trim();
                if (!label) label = el.getAttribute('aria-label') || el.placeholder || '';

                fields.push({
                    identifier: el.name || el.id || label.slice(0, 50),
                    label: label.slice(0, 100),
                    placeholder: (el.placeholder || '').slice(0, 100),
                    type: el.type || el.tagName.toLowerCase(),
                });
            });
            return fields;
        }""")

        if not fields_info:
            return {}

        profile_keys = [k for k, v in profile.items() if v]

        prompt = (
            f"Map these HTML form fields to user profile keys.\n\n"
            f"Form fields:\n{json.dumps(fields_info, indent=2)}\n\n"
            f"Available profile keys with values: {profile_keys}\n\n"
            f"Return ONLY a JSON object mapping form field identifiers to profile keys.\n"
            f'Example: {{"first-name": "full_name", "email-input": "email"}}\n'
            f"Only include fields that have a matching profile key. Return {{}} if no matches."
        )

        try:
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            resp = await client.chat.completions.create(
                model=os.getenv("LLM_MODEL", OPENAI_MODEL),
                messages=[
                    {"role": "system", "content": "You map HTML form fields to user data keys. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            raw = resp.choices[0].message.content or "{}"
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
            return json.loads(raw)
        except Exception as e:
            logger.warning("AI field mapping failed: %s", e)
            # Fallback: simple heuristic matching
            return self._heuristic_mapping(fields_info, profile)

    @staticmethod
    def _heuristic_mapping(fields: list, profile: dict) -> dict:
        """Simple keyword-based fallback mapping."""
        mapping = {}
        HINTS = {
            "name": "full_name", "full_name": "full_name", "first_name": "full_name",
            "email": "email", "mail": "email",
            "phone": "phone", "tel": "phone", "mobile": "phone",
            "github": "github_url", "linkedin": "linkedin_url",
            "portfolio": "portfolio_url", "website": "portfolio_url",
            "skill": "skills", "experience": "experience_level",
            "team": "team_name", "diet": "dietary_restrictions",
            "tshirt": "tshirt_size", "shirt": "tshirt_size", "size": "tshirt_size",
            "country": "country", "city": "city",
            "university": "university", "school": "university", "college": "university",
            "grad": "graduation_year", "bio": "bio", "about": "bio",
        }
        for field in fields:
            identifier = (field.get("identifier", "") + " " + field.get("label", "")).lower()
            for hint, profile_key in HINTS.items():
                if hint in identifier and profile.get(profile_key):
                    mapping[field["identifier"]] = profile_key
                    break
        return mapping


# ─── Factory ──────────────────────────────────────────────────

def create_registration_tools() -> list[BaseTool]:
    """Create all hackathon registration tools."""
    return [
        GetUserProfileTool(),
        SaveUserProfileTool(),
        DetectRegistrationFormTool(),
        AutoFillAndRegisterTool(),
    ]
