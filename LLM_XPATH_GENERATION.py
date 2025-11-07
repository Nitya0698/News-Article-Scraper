import json
from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = """
Analyze this HTML structure and generate the XPATH selectors,

Be as Generic as possible, so that the XPATH can apply to multiple articles

GOOD XPATH EXAMPLES:
- Author: //a[contains(@class, 'author')] | //span[contains(@class, 'byline')]
- Date: //time[@datetime] | //span[contains(@class, 'date')] | //div[contains(@class, 'publish')]
- Title: //h1 | //h2[contains(@class, 'title')]
- Content: //article//p | //div[contains(@class, 'content')]//p | //div[contains(@class, 'story')]//p

BAD XPATH EXAMPLES (too specific):
- //div[@class='author-name-component-2024'] (exact class match - will break)
- //a[contains(@href, 'author-specific-name')] (too specific)
- //span[contains(text(), 'Updated:')] (hardcoded text - language dependent)

Return ONLY valid JSON in this exact format, with no additional text or explanation:
{
  "author": "flexible_xpath_here",
  "time": "flexible_xpath_here",
  "date": "flexible_xpath_here",
  "title": "flexible_xpath_here",
  "content": "flexible_xpath_here"
}

Generate XPath selectors for:
- author: The person who wrote the article (look for author/byline/writer patterns)
- time: Time of day the article was published (look for time/datetime attributes)
- date: Date the article was published (look for date/datetime/published patterns)
- title: Main headline/title of the article (usually h1 or h2)
- content: All paragraph elements containing the article text (target the container, use //p)

Return ONLY the JSON object, nothing else."""

def generate_initial_xpaths(cleaned_html, client):

    # Initialize OpenAI client
    # ===========================

    client = OpenAI(api_key=api_key)
    user_prompt = cleaned_html
    #FEED THE PAGE INTO THE LLM AND GET NEW XPATH

    response_ai = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )
    # Get the response content
    ai_response = response_ai.choices[0].message.content.strip()
    print("OpenAI Response:")
    print(ai_response)
    print()

    try:
        xpaths = json.loads(ai_response)
        return xpaths
    except json.JSONDecodeError as e:
        print(f"✗ Error parsing LLM response: {e}")
        return {
            "author": "",
            "time": "",
            "date": "",
            "title": "",
            "content": ""
        }

CORRECTION_PROMPT = """
The initial XPath selectors failed to extract some fields correctly. 

CURRENT XPATHS:
{current_xpaths}

FAILED FIELDS AND FEEDBACK:
{feedback}

Analyze this HTML structure again and generate CORRECTED XPath selectors ONLY for the failed fields.

Guidelines:
- Be more flexible with class names (use contains() instead of exact matches)
- Try multiple alternative selectors using | (OR operator)
- Look for semantic HTML tags (time, article, author, etc.)
- Consider datetime attributes for date/time fields
- For content, ensure you're capturing all article paragraphs, not navigation/ads

GOOD XPATH EXAMPLES:
- Author: //a[contains(@class, 'author')] | //span[contains(@class, 'byline')] | //div[contains(@class, 'writer')]
- Date: //time[@datetime] | //span[contains(@class, 'date')] | //meta[@property='article:published_time']/@content
- Title: //h1 | //h2[contains(@class, 'title')] | //meta[@property='og:title']/@content
- Content: //article//p | //div[contains(@class, 'content')]//p | //div[contains(@class, 'article-body')]//p

Return ONLY valid JSON with ONLY the failed fields in this exact format:
{{
  "field_name": "corrected_xpath_here"
}}

For example, if only author and date failed:
{{
  "author": "//span[contains(@class, 'byline')] | //a[contains(@class, 'author')]",
  "date": "//time[@datetime] | //meta[@property='article:published_time']/@content"
}}

Return ONLY the JSON object for failed fields, nothing else."""

def retry_failed_xpaths(failed_fields, feedback, current_xpaths, cleaned_html, client):

    print("Retrying to generate Fields Correctly:")
    print(f"Failed fields: {failed_fields}")
    print(f"Feedback: {feedback}")

    current_xpaths_str = json.dumps(current_xpaths, indent=2)
    feedback_str = json.dumps(feedback, indent=2)

    print("current_xpaths_Str-  ", current_xpaths_str)
    print("feedback_str- ", feedback_str)

    # Create the correction prompt
    correction_prompt = CORRECTION_PROMPT.format(
        current_xpaths=current_xpaths_str,
        feedback=feedback_str
    )

    # Call OpenAI for corrections
    response_ai = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": correction_prompt},
            {"role": "user", "content": cleaned_html}
        ],
        temperature=0.3
    )

    ai_response = response_ai.choices[0].message.content.strip()
    # print("OpenAI Correction Response:")
    # print(ai_response)
    # print()
    
    try:
        corrected_xpaths = json.loads(ai_response)
        # print(f"Successfully parsed {len(corrected_xpaths)} corrected XPaths")
        return corrected_xpaths
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response: {e}")
        return {}

DIRECT_EXTRACTION_PROMPT = """
You are a precise web scraper. Extract the requested fields DIRECTLY from this HTML content.

FAILED FIELDS TO EXTRACT:
{failed_fields}

FEEDBACK ON WHY XPATHS FAILED:
{feedback}

Your task: Read the HTML and extract the actual text content for each failed field.

Guidelines:
- For author: Extract the article author's name (just the name, no extra text)
- For date: Extract the publication date in format "Month DD, YYYY" (e.g., "November 06, 2025")
- For time: Extract the publication time in format "HH:MM AM/PM IST" (e.g., "02:30 PM IST")
- For title: Extract the main article headline/title
- For content: Extract the main article text (all paragraphs, no ads/navigation)

Return ONLY valid JSON in this exact format:
{{
  "field_name": "extracted_text_here"
}}

For example:
{{
  "author": "John Smith",
  "date": "November 06, 2025",
  "time": "02:30 PM IST",
  "title": "Article Headline Goes Here",
  "content": "Full article text content goes here..."
}}

Return ONLY the JSON object with the failed fields, nothing else."""

def direct_llm_extraction(failed_fields, feedback, cleaned_html, client):
    """
    Last resort: Directly extract field values using LLM when XPaths fail.
    Returns a dictionary with extracted text values (not XPaths).
    """
    print("\n" + "="*60)
    print("FALLBACK: Direct LLM Extraction (XPaths failed)")
    print("="*60)
    print(f"Extracting fields directly: {failed_fields}")
    
    failed_fields_str = ", ".join(failed_fields)
    feedback_str = json.dumps(feedback, indent=2)
    
    # Create the extraction prompt
    extraction_prompt = DIRECT_EXTRACTION_PROMPT.format(
        failed_fields=failed_fields_str,
        feedback=feedback_str
    )
    
    # Call OpenAI for direct extraction
    response_ai = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": extraction_prompt},
            {"role": "user", "content": cleaned_html}
        ],
        temperature=0.3
    )
    
    ai_response = response_ai.choices[0].message.content.strip()
    # print("LLM Direct Extraction Response:")
    # print(ai_response)
    # print()
    
    try:
        extracted_data = json.loads(ai_response)
        print(f"Successfully extracted {len(extracted_data)} fields directly")
        return extracted_data
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response: {e}")
        return {}
