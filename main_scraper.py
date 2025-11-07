import requests
import tldextract
import sqlite3
from lxml import html
from dateutil import parser
import re
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from dotenv import load_dotenv
import os
from keyword_matcher import compare_texts
from LLM_XPATH_GENERATION import generate_initial_xpaths, retry_failed_xpaths


#SET TO FALSE IF LLM USAGE TOO HIGH, ENSURES ALL FIELDS ARE FETCHED IN CASE NO XPATH WORKS
ENABLE_DIRECT_LLM_FALLBACK = True 
MAX_RETRIES = 3
retry_count = 0

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

#LLM INITIALISATION
# =============================================== 
client = OpenAI(api_key=api_key)

# Load persistent LLM call counter from environment
llm_call_count = int(os.getenv("TOTAL_LLM_CALLS", 0))
starting_count = llm_call_count
print(f"Starting LLM call count: {llm_call_count}")

def extract_datetime_from_elements(elements, field_name="datetime"):
    """Extract date/time from elements, checking datetime attribute first."""
    if not elements:
        return "", ""
    
    # Strategy 1: Check datetime/content attribute (most reliable)
    for elem in elements:
        if hasattr(elem, 'get'):
            # Check both 'datetime' (for <time> tags) and 'content' (for <meta> tags)
            datetime_str = elem.get('datetime') or elem.get('content')
            if datetime_str:
                try:
                    dt = parser.parse(datetime_str)
                    return dt.strftime("%B %d, %Y"), dt.strftime("%I:%M %p IST")
                except:
                    pass
    
    # Strategy 2: Parse text content
    text_content = ' '.join([elem.text_content().strip() for elem in elements if hasattr(elem, 'text_content')])
    if not text_content.strip():
        return "", ""
    
    # Clean text (keywords_to_remove is built-in here)
    keywords_to_remove = ["updated", "published", "posted", "last updated", "modified"]
    cleaned_text = text_content
    for keyword in keywords_to_remove:
        cleaned_text = re.sub(rf'\b{keyword}\b', "", cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    try:
        dt = parser.parse(cleaned_text, fuzzy=True)
        return dt.strftime("%B %d, %Y"), dt.strftime("%I:%M %p IST")
    except:
        return text_content, ""

def extract_content_with_xpaths(tree, author_xpath, time_xpath, date_xpath, title_xpath, content_xpath):
    # Extract author
    author = tree.xpath(author_xpath)
    author_text = ' '.join([
        a.text_content().strip() if hasattr(a, 'text_content') else str(a).strip() 
        for a in author
    ]) if author else ""
    
    # Extract date and time
    date_elements = tree.xpath(date_xpath)
    time_elements = tree.xpath(time_xpath)
    
    # Check if date and time XPaths are the same
    if date_xpath == time_xpath:
        date_cleaned, time_cleaned = extract_datetime_from_elements(date_elements, "datetime")
    else:
        date_result = extract_datetime_from_elements(date_elements, "date")
        time_result = extract_datetime_from_elements(time_elements, "time")
        date_cleaned = date_result[0] if date_result[0] else ""
        time_cleaned = time_result[1] if time_result[1] else time_result[0]
    
    # Extract title - handle both elements and attribute values
    titles = tree.xpath(title_xpath)
    title_text = ' '.join([
        a.text_content().strip() if hasattr(a, 'text_content') else str(a).strip() 
        for a in titles
    ]) if titles else ""
    
    # Extract content
    content = tree.xpath(content_xpath)
    content_text = ' '.join([
        a.text_content().strip() if hasattr(a, 'text_content') else str(a).strip() 
        for a in content
    ]) if content else ""
    
    return author_text, date_cleaned, time_cleaned, title_text, content_text

def validate_extracted_fields(author_text, date_cleaned, time_cleaned, title_text, content_text):
    failed_fields = []
    feedback = {}
    
    # Check author
    if not author_text or author_text.strip() == "":
        failed_fields.append('author')
        feedback['author'] = "Empty Author field"
    elif len(author_text) > 25:
        failed_fields.append('author')
        feedback['author'] = 'Author length too big'
    
    # Check date
    if not date_cleaned or date_cleaned.strip() == "":
        failed_fields.append('date')
        feedback['date'] = "Empty date field"
    
    # Check time
    if not time_cleaned or time_cleaned.strip() == "":
        failed_fields.append('time')
        feedback['time'] = "Empty time field"
    
    # Check title
    if not title_text or title_text.strip() == "":
        failed_fields.append('title')
        feedback['title'] = "Empty title field"
    elif len(title_text.strip()) < 10:
        failed_fields.append('title')
        feedback['title'] = f"Title too short (only {len(title_text)} chars)"
    
    # Check content
    if not content_text or content_text.strip() == "":
        failed_fields.append('content')
        feedback['content'] = "Empty content field"
    elif len(content_text.strip()) < 100:
        failed_fields.append('content')
        feedback['content'] = f"Content too short (only {len(content_text)} chars)"
    
    # Check title-content match
    match_result = compare_texts(title_text, content_text, threshold=50, verbose=True)
    if match_result == 0:
        failed_fields.append('Content')
        feedback['Title Content'] = "Title and Content Do not match"
    
    return failed_fields, feedback




# URL INPUT AND EXTRACTION OF DOMAIN
# ======================================
url = input("Enter a URL: ").strip()

extracted = tldextract.extract(url)
domain = extracted.domain
print("\nExtracted Domain- " + domain)
response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})

conn = sqlite3.connect('articles.db')
cursor = conn.cursor()

# Clean HTML for potential LLM usage
# ===================================
print("\nCleaning up HTML...")
soup = BeautifulSoup(response.text, 'html.parser')

# Remove unnecessary tags to save tokens
for script in soup.find_all('script'):
    script.decompose()
for style in soup.find_all('style'):
    style.decompose()
for iframe in soup.find_all('iframe'):
    iframe.decompose()
for tag in soup.find_all(['nav', 'header', 'footer', 'aside']):
    tag.decompose()

cleaned_html = str(soup)
print("HTML cleaned")

tree = html.fromstring(response.content)
print("HTML tree created for XPath testing")

#CHECKING IF DOMAIN ALREADY EXISTS IN DATABASE
# ===============================================

cursor.execute("SELECT * FROM TRACKING_DOMAINS WHERE Domain = ?", (domain,))
column_names = [description[0] for description in cursor.description]
print("\nColumn names:", column_names)
result = cursor.fetchone()

if result:
    print(f"Domain '{domain}' already exists in database!")
    
    # Fetch pipe-separated XPaths from TRACKING_DOMAINS
    # Structure: Domain, TotalFailures, AuthorXPath, TitleXPath, DateXPath, TimeXPath, ContentXPath
    author_xpaths_str = result[2] if result[2] else ""
    title_xpaths_str = result[3] if result[3] else ""
    date_xpaths_str = result[4] if result[4] else ""
    time_xpaths_str = result[5] if result[5] else ""
    content_xpaths_str = result[6] if result[6] else ""
    
    print("\nTrying existing XPaths from database...")
    
    # Initialize variables for working XPaths
    author_xpath = None
    title_xpath = None
    date_xpath = None
    time_xpath = None
    content_xpath = None
    
    # Try each Author XPath until one works
    if author_xpaths_str:
        author_xpaths_list = [x.strip() for x in author_xpaths_str.split("|")]
        for xpath in author_xpaths_list:
            try:
                author_result = tree.xpath(xpath)
                author_text_test = ' '.join([
                    a.text_content().strip() if hasattr(a, 'text_content') else str(a).strip() 
                    for a in author_result
                ]) if author_result else ""
                
                # Quick validation
                if author_text_test and author_text_test.strip() != "" and len(author_text_test) <= 25:
                    author_xpath = xpath
                    # print(f"Found working Author XPath: {xpath}")
                    break
            except:
                continue
    
    # Try each Title XPath until one works
    if title_xpaths_str:
        title_xpaths_list = [x.strip() for x in title_xpaths_str.split("|")]
        for xpath in title_xpaths_list:
            try:
                title_result = tree.xpath(xpath)
                title_text_test = ' '.join([
                    a.text_content().strip() if hasattr(a, 'text_content') else str(a).strip() 
                    for a in title_result
                ]) if title_result else ""
                
                # Quick validation
                if title_text_test and title_text_test.strip() != "" and len(title_text_test.strip()) >= 10:
                    title_xpath = xpath
                    # print(f"Found working Title XPath: {xpath}")
                    break
            except:
                continue
    
    # Try each Date XPath until one works
    if date_xpaths_str:
        date_xpaths_list = [x.strip() for x in date_xpaths_str.split("|")]
        for xpath in date_xpaths_list:
            try:
                date_result = tree.xpath(xpath)
                date_text_test, _ = extract_datetime_from_elements(date_result, "date")
                
                # Quick validation
                if date_text_test and date_text_test.strip() != "":
                    date_xpath = xpath
                    # print(f"Found working Date XPath: {xpath}")
                    break
            except:
                continue
    
    # Try each Time XPath until one works
    if time_xpaths_str:
        time_xpaths_list = [x.strip() for x in time_xpaths_str.split("|")]
        for xpath in time_xpaths_list:
            try:
                time_result = tree.xpath(xpath)
                _, time_text_test = extract_datetime_from_elements(time_result, "time")
                
                # Quick validation
                if time_text_test and time_text_test.strip() != "":
                    time_xpath = xpath
                    # print(f"Found working Time XPath: {xpath}")
                    break
            except:
                continue
    
    # Try each Content XPath until one works
    if content_xpaths_str:
        content_xpaths_list = [x.strip() for x in content_xpaths_str.split("|")]
        for xpath in content_xpaths_list:
            try:
                content_result = tree.xpath(xpath)
                content_text_test = ' '.join([
                    a.text_content().strip() if hasattr(a, 'text_content') else str(a).strip() 
                    for a in content_result
                ]) if content_result else ""
                
                # Quick validation
                if content_text_test and len(content_text_test.strip()) >= 100:
                    content_xpath = xpath
                    # print(f"Found working Content XPath: {xpath}")
                    break
            except:
                continue
    
    # Check if any fields still don't have working XPaths
    fields_needing_llm = []
    if not author_xpath:
        fields_needing_llm.append('author')
        # print("No working Author XPath found")
    if not title_xpath:
        fields_needing_llm.append('title')
        # print("No working Title XPath found")
    if not date_xpath:
        fields_needing_llm.append('date')
        # print("No working Date XPath found")
    if not time_xpath:
        fields_needing_llm.append('time')
        # print("No working Time XPath found")
    if not content_xpath:
        fields_needing_llm.append('content')
        # print("No working Content XPath found")
    
    # If any fields need XPaths, call LLM for ONLY those fields
    if fields_needing_llm:
        # print(f"\nCalling LLM for fields: {fields_needing_llm}")
        llm_call_count += 1 
        
        # Build current_xpaths dict with what we have
        current_xpaths = {
            "author": author_xpath if author_xpath else "",
            "time": time_xpath if time_xpath else "",
            "date": date_xpath if date_xpath else "",
            "title": title_xpath if title_xpath else "",
            "content": content_xpath if content_xpath else ""
        }
        
        # Create feedback for failed fields
        feedback = {field: f"No working XPath found for {field}" for field in fields_needing_llm}
        
        # Call LLM for only the failed fields
        new_xpaths = retry_failed_xpaths(
            failed_fields=fields_needing_llm,
            feedback=feedback,
            current_xpaths=current_xpaths,
            cleaned_html=cleaned_html,
            client=client
        )
        
        # Update only the fields that LLM generated
        if 'author' in new_xpaths and not author_xpath:
            author_xpath = new_xpaths['author']
            # print(f"LLM generated Author XPath: {author_xpath}")
        if 'time' in new_xpaths and not time_xpath:
            time_xpath = new_xpaths['time']
            # print(f"LLM generated Time XPath: {time_xpath}")
        if 'date' in new_xpaths and not date_xpath:
            date_xpath = new_xpaths['date']
            # print(f"LLM generated Date XPath: {date_xpath}")
        if 'title' in new_xpaths and not title_xpath:
            title_xpath = new_xpaths['title']
            # print(f"LLM generated Title XPath: {title_xpath}")
        if 'content' in new_xpaths and not content_xpath:
            content_xpath = new_xpaths['content']
            # print(f"LLM generated Content XPath: {content_xpath}")

else:
    print(f"\nDomain '{domain}' not found in database, Calling LLM to Generate new XPATH's and add into database")
    
    # Generate XPaths using LLM helper function
    xpaths = generate_initial_xpaths(cleaned_html, client)
    llm_call_count += 1 

    author_xpath = xpaths.get("author", "")
    time_xpath = xpaths.get("time", "")
    date_xpath = xpaths.get("date", "")
    title_xpath = xpaths.get("title", "")
    content_xpath = xpaths.get("content", "")

    # INSERT into TRACKING_DOMAINS (not XPATHS)
    cursor.execute('''
        INSERT INTO TRACKING_DOMAINS (Domain, TotalFailures, AuthorXPath, TitleXPath, DateXPath, TimeXPath, ContentXPath)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (domain, 0, author_xpath, title_xpath, date_xpath, time_xpath, content_xpath))
    
    conn.commit()
    print("New domain added to TRACKING_DOMAINS")


author_text, date_cleaned, time_cleaned, title_text, content_text = extract_content_with_xpaths(
    tree, author_xpath, time_xpath, date_xpath, title_xpath, content_xpath
)

# Validate whether the Fields are correct or not
print("\nChecking whether fields are correct or not-\n")
failed_fields, feedback = validate_extracted_fields(
    author_text, date_cleaned, time_cleaned, title_text, content_text
)

print(failed_fields, feedback)

#RETRYING TO GENERATE XPATHS


direct_extraction_used = False  # Track if fallback was needed

while failed_fields and retry_count < MAX_RETRIES:

    print("RETRYING TO GENERATE XPATHS-")
    print("Retry Attempt- ", retry_count)
    retry_count +=1
    llm_call_count += 1 


    # Store current XPaths
    current_xpaths = {
        "author": author_xpath,
        "time": time_xpath,
        "date": date_xpath,
        "title": title_xpath,
        "content": content_xpath
    }

    # Get corrected XPaths from LLM
    corrected_xpaths = retry_failed_xpaths(
        failed_fields=failed_fields,
        feedback=feedback,
        current_xpaths=current_xpaths,
        cleaned_html=cleaned_html,
        client=client
    )

        # Update the XPath variables with corrections
    if 'author' in corrected_xpaths:
        author_xpath = corrected_xpaths['author']
        # print(f"Updated author XPath: {author_xpath}")
    if 'time' in corrected_xpaths:
        time_xpath = corrected_xpaths['time']
        # print(f"Updated time XPath: {time_xpath}")
    if 'date' in corrected_xpaths:
        date_xpath = corrected_xpaths['date']
        # print(f"Updated date XPath: {date_xpath}")
    if 'title' in corrected_xpaths:
        title_xpath = corrected_xpaths['title']
        # print(f"Updated title XPath: {title_xpath}")
    if 'content' in corrected_xpaths or 'Content' in corrected_xpaths:
        content_xpath = corrected_xpaths.get('content') or corrected_xpaths.get('Content')
        # print(f"Updated content XPath: {content_xpath}")

        # print(f"\nRe-extracting content (attempt {retry_count})...")
    author_text, date_cleaned, time_cleaned, title_text, content_text = extract_content_with_xpaths(
        tree, author_xpath, time_xpath, date_xpath, title_xpath, content_xpath
    )

    # Re-validate
    print(f"\nRe-validating (attempt {retry_count})...")
    failed_fields, feedback = validate_extracted_fields(
        author_text, date_cleaned, time_cleaned, title_text, content_text
    )

    if not failed_fields:
        print(f"\nAll fields validated successfully after {retry_count} attempt(s)!")
        break
    else:
        print(f"\nStill have {len(failed_fields)} failed field(s): {failed_fields}")
        if retry_count < MAX_RETRIES:
            print("Will retry with new XPaths...")
        else:
            print(f"Max retries ({MAX_RETRIES}) reached. Proceeding with current data.")


if not failed_fields:
    print("\nAll fields validated successfully!")
else:
    print(f"\nFinal result: {len(failed_fields)} field(s) still failed after all retries.")
    print(f"Failed fields: {failed_fields}")
    print(f"Feedback: {feedback}")
    
    # FALLBACK: Direct LLM extraction if enabled
    if ENABLE_DIRECT_LLM_FALLBACK:
        print("\nAttempting direct LLM extraction as fallback...")
        direct_extraction_used = True  # Set flag
        llm_call_count += 1 

        
        from LLM_XPATH_GENERATION import direct_llm_extraction
        
        # Call LLM to directly extract the content
        extracted_data = direct_llm_extraction(
            failed_fields=failed_fields,
            feedback=feedback,
            cleaned_html=cleaned_html,
            client=client
        )
        
        # Update variables with directly extracted data
        if 'author' in extracted_data and 'author' in failed_fields:
            author_text = extracted_data['author']
            # print(f"Direct extraction - Author: {author_text}")
        
        if 'date' in extracted_data and 'date' in failed_fields:
            date_cleaned = extracted_data['date']
            # print(f"Direct extraction - Date: {date_cleaned}")
        
        if 'time' in extracted_data and 'time' in failed_fields:
            time_cleaned = extracted_data['time']
            # print(f"Direct extraction - Time: {time_cleaned}")
        
        if 'title' in extracted_data and 'title' in failed_fields:
            title_text = extracted_data['title']
            # print(f"Direct extraction - Title: {title_text}")
        
        if 'content' in extracted_data and ('content' in failed_fields or 'Content' in failed_fields):
            content_text = extracted_data['content']
            # print(f"Direct extraction - Content: {content_text[:50]}...")
        
        print("\nFallback extraction complete - data will be saved to database")
    else:
        print("\nDirect LLM fallback is disabled. Proceeding with partial data.")


# Track retry statistics and successful XPaths (ONLY for validated fields)
# =========================================================================

# Validate each field to determine which XPaths are "correct"
validated_xpaths = {}

# Check author validation
if author_text and author_text.strip() != "" and len(author_text) <= 25:
    validated_xpaths['author'] = author_xpath
    # print(f"Author XPath validated: {author_xpath}")

# Check date validation
if date_cleaned and date_cleaned.strip() != "":
    validated_xpaths['date'] = date_xpath
    # print(f"Date XPath validated: {date_xpath}")

# Check time validation
if time_cleaned and time_cleaned.strip() != "":
    validated_xpaths['time'] = time_xpath
    # print(f"Time XPath validated: {time_xpath}")

# Check title validation
if title_text and title_text.strip() != "" and len(title_text.strip()) >= 10:
    validated_xpaths['title'] = title_xpath
    # print(f"Title XPath validated: {title_xpath}")

# Check content validation (length >= 100 AND matches with title)
if content_text and content_text.strip() != "" and len(content_text.strip()) >= 100:
    match_result = compare_texts(title_text, content_text, threshold=50, verbose=False)
    if match_result != 0:  # Title and content match
        validated_xpaths['content'] = content_xpath
        # print(f"Content XPath validated: {content_xpath}")

# Only proceed if we have at least one validated XPath
if validated_xpaths:
    # Check if domain already exists in tracking table
    cursor.execute("SELECT * FROM TRACKING_DOMAINS WHERE Domain = ?", (domain,))
    tracking_result = cursor.fetchone()
    
    if tracking_result:
        # Domain exists - append only NEW validated XPaths with 5-XPath cap
        existing_total = tracking_result[1]
        existing_author = tracking_result[2] if tracking_result[2] else ""
        existing_title = tracking_result[3] if tracking_result[3] else ""
        existing_date = tracking_result[4] if tracking_result[4] else ""
        existing_time = tracking_result[5] if tracking_result[5] else ""
        existing_content = tracking_result[6] if tracking_result[6] else ""
        
        # Helper function to append with cap
        def append_xpath_with_cap(existing_str, new_xpath, cap=5):
            """Append new XPath if not already present, keep only last 'cap' XPaths"""
            if not new_xpath or not new_xpath.strip():
                return existing_str
            
            # Split existing XPaths and clean
            existing_list = [x.strip() for x in existing_str.split("|") if x.strip()] if existing_str else []
            
            # Check if new XPath already exists
            if new_xpath not in existing_list:
                existing_list.append(new_xpath)
                # Keep only last 'cap' XPaths (most recent)
                existing_list = existing_list[-cap:]
            
            return " | ".join(existing_list)
        
        # Append new validated XPaths with 5-XPath cap
        new_author = existing_author
        if 'author' in validated_xpaths:
            new_author = append_xpath_with_cap(existing_author, validated_xpaths['author'], cap=5)

        new_title = existing_title
        if 'title' in validated_xpaths:
            new_title = append_xpath_with_cap(existing_title, validated_xpaths['title'], cap=5)

        new_date = existing_date
        if 'date' in validated_xpaths:
            new_date = append_xpath_with_cap(existing_date, validated_xpaths['date'], cap=5)

        new_time = existing_time
        if 'time' in validated_xpaths:
            new_time = append_xpath_with_cap(existing_time, validated_xpaths['time'], cap=5)

        new_content = existing_content
        if 'content' in validated_xpaths:
            new_content = append_xpath_with_cap(existing_content, validated_xpaths['content'], cap=5)

        # Update existing record
        cursor.execute('''
            UPDATE TRACKING_DOMAINS 
            SET TotalFailures = ?, 
                AuthorXPath = ?, 
                TitleXPath = ?, 
                DateXPath = ?, 
                TimeXPath = ?, 
                ContentXPath = ?,
                LastUpdated = CURRENT_TIMESTAMP
            WHERE Domain = ?
        ''', (existing_total + retry_count, new_author, new_title, new_date, new_time, new_content, domain))
        # print(f"Updated tracking data for domain '{domain}'")
        
    else:
        # This shouldn't happen now (since we insert in Section 1), but keep as fallback
        cursor.execute('''
            INSERT INTO TRACKING_DOMAINS (Domain, TotalFailures, AuthorXPath, TitleXPath, DateXPath, TimeXPath, ContentXPath)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            domain, 
            retry_count,
            validated_xpaths.get('author', None),
            validated_xpaths.get('title', None),
            validated_xpaths.get('date', None),
            validated_xpaths.get('time', None),
            validated_xpaths.get('content', None)
        ))
        # print(f"Created tracking record for domain '{domain}'")
    
    conn.commit()
else:
    print(f"No validated XPaths to track for domain '{domain}'")


cursor.execute('''
    INSERT OR REPLACE INTO ARTICLES (Domain, URL, Author, Time, Date, Title, Content)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', (domain, url, author_text, time_cleaned, date_cleaned, title_text, content_text))

conn.commit()


print("Saved to database succesfully!")

print(f"\nDomain: {domain}")
print(f"Author: {author_text}")
print(f"Date: {date_cleaned}")
print(f"Time: {time_cleaned}")
print(f"Title: {title_text}")
content_words = content_text.split()[:50]
content_preview = ' '.join(content_words) + ("..." if len(content_text.split()) > 50 else "")
print(f"Content: {content_preview}")
print(f"\nDirect LLM Extraction Used: {direct_extraction_used}")
print(f"Total LLM API Calls (This Run): {llm_call_count - starting_count}")
print(f"Total LLM API Calls (All Time): {llm_call_count}")

# Update .env file with new count
from dotenv import set_key
set_key('.env', 'TOTAL_LLM_CALLS', str(llm_call_count))

conn.close()