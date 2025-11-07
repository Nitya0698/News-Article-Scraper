Dynamic/Self-Updating python based news-article scraper.

install using 
bash setup.sh

Then python3 main_scraper.py
or python3 batch_scraper.py

batch_scraper will need a .txt file as an input containing links to all news articles, Sample_articles.txt is provided, 
run using "python3 batch_scraper.py sample_articles.txt"

Flow of Program-

Given an input URL, Extracts Domain name for it, 
domain = extracted.domain

(IMPORTANT, There is currently no check in place for veryfying whether the URL is actually a news Article, it is assumed by default)

First Check Databse if Domain name already exists
1. Author
2. Date Published
3. Time Published
4. Title of Article
5. Content of Article

If Domain Name is not in database, Call LLM to fetch fresh XPATHS and store them.

otherwise fetch previous XPATHS, loop through each of them and check if validation works or not.

Now fetch the content using extract_content_with_xpaths()

Validate each field using validate_extracted_fields()

Constraints Considered for validation-
1. Author not empty and less than 25 words
2. Date not empty
3. Time not empty
4. Title not empty and too short < 10 words
5. Content not empty and not too short < 100 words
6. Key word extraction in Title and Content, if keywords overlap atleast 50% then validate

(All of these settings can be adjusted in code)

Next if any field Fails Validation, Only the Fields that failed validation are sent again to the LLM, which now returns a new XPATH after scanning the article again, to save token cost the HTML is cleaned up first using BeautifulSoup
cleaned_html = str(soup)

Then with the new fields -
Validation is done again, calling the validate_extracted_fields,
This is done upto 3 times, which can be changed by changing this variable.
MAX_RETRIES = 3

If even after MAX_RETRIES, The LLM fails to fetch the correct XPATH, then a failsafe can be set, called ENABLE_DIRECT_LLM_FALLBACK = True 
This will send all failed fields to the LLM and request the content directly.

All content is then finally saved to the ARTICLES table.

The XPATHS that worked/were validated are then uploaded to the TRACKING_DOMAINS table.

Only the most_recent 5 XPATHS are used, so it is kind of self-healing and updating.




Helper Files-

LLM_XPATH_GENERATION.py 

(Imported functions, contains LLM Prompts that fetch XPATHS)

keyword_matcher.py 

(Imported function, contains logic for keyword matching between Title and Content)

Create_Tracking_Domains_Database.py
Create_Articles_Database.py

(Contains Database Schema, will create a new database when run)

batch_scraper.py

(Batch scraper, Can create a articles.txt containing Article URL's and will run them one by one)

Helper Functions in Main_Scraper.py-

1. extract_datetime_from_elements()
//Extract datetime from Xpath

2. extract_content_with_xpaths()
//Extract Content using xpath

3. validate_extracted_fields
// Validate using conditions for verifying content etc.





TL:DR;-

Set API key in env,
OPENAI_API_KEY = ""

TOTAL_LLM_CALLS='0'(will auto-update no need to touch, unless want to reset)

In Main_Scraper.py

MAX_RETRIES = 3 (Max amount of times LLM is called in case base XPATHS fail)
ENABLE_DIRECT_LLM_FALLBACK = True (Set hard-fallback in case XPATHS fail)

                        WEB SCRAPER FLOW


START: Input URL (No check for veryfying if news article)
  │
  ├─► Extract Domain & Clean HTML
  │    └─► Remove scripts, styles, nav, header, footer
  │
  ├─► Check Database
  │    │
  │    ├─► Domain EXISTS?
  │    │    ├─► YES: Load existing XPaths (pipe-separated)
  │    │    │    └─► Try each XPath until one works
  │    │    │
  │    │    └─► NO: Generate new XPaths using LLM
  │    │         └─► Use generated XPaths
  │    │
  │    └─► Extract Data (Author, Date, Time, Title, Content)
  │
  ├─► Validate Extracted Fields
  │    │
  │    ├─► ALL VALID?
  │    │    │
  │    │    ├─► YES: ✓ Proceed to Save
  │    │    │
  │    │    └─► NO: Fields failed validation
  │    │         │
  │    │         ├─► Retry Count < Max (3)?
  │    │         │    │
  │    │         │    ├─► YES: Generate new XPaths for failed fields
  │    │         │    │    └─► Loop back to Extract & Validate
  │    │         │    │
  │    │         │    └─► NO: Max retries reached
  │    │         │         │
  │    │         │         └─► Direct LLM Fallback Enabled?
  │    │         │              │
  │    │         │              ├─► YES: LLM directly extracts missing data
  │    │         │              │    └─► Update failed fields with LLM results
  │    │         │              │
  │    │         │              └─► NO: Proceed with partial data
  │    │
  │    └─► Update Tracking Database
  │         └─► Store validated XPaths (max 5 per field)
  │         └─► Increment retry counter
  │
  ├─► Save Article to Database
  │    └─► Store: Domain, URL, Author, Time, Date, Title, Content
  │
  └─► Display Results
       ├─► Show extracted data preview
       ├─► Direct LLM usage: YES/NO
       ├─► LLM calls this run
       └─► Total LLM calls (all time)

END


KEY VALIDATION RULES:
  • Author: Not empty, length ≤ 25 chars
  • Date: Not empty
  • Time: Not empty
  • Title: Not empty, length ≥ 10 chars
  • Content: Not empty, length ≥ 100 chars, matches title (50% threshold)





