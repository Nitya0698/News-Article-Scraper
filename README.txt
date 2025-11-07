Dynamic/Self-Updating Python-based news-article scraper.


Install using:

    bash setup.sh

Then run:
    python3 main_scraper.py 
or
    python3 batch_scraper.py sample_articles.txt


IMPORTANT: There is currently no check to verify whether the URL is a valid news article; it is assumed by default.

Model_Used- 'gpt-4o-mini'
(0.30$-0.50$ per 300-400 articles/links)

Flow of the program:
    Given an input URL, the domain is extracted using `domain = extracted.domain`.
    First, the database is checked to see if the domain already exists for the following fields:

        1. Author
        2. Date Published
        3. Time Published
        4. Title of Article
        5. Content of Article

    If the domain is not in the database, the LLM is called to fetch fresh XPaths and store them.
    Otherwise, previous XPaths are fetched, validated, and used to extract content via `extract_content_with_xpaths()`.
    Each field is validated using `validate_extracted_fields()`.

    Validation constraints include:

        1. Author not empty and < 25 words
        2. Date not empty
        3. Time not empty
        4. Title not empty and > 10 words
        5. Content not empty and > 100 words
        6. Keyword overlap between Title and Content ≥ 50%
        (These settings can be adjusted in the code)

    If any field fails validation, only the failed fields are sent again to the LLM,
    which returns a new XPath after scanning the cleaned HTML using BeautifulSoup:
        cleaned_html = str(soup)
    Validation is retried up to `MAX_RETRIES = 2`.
    If fields still fail, setting `ENABLE_DIRECT_LLM_FALLBACK = True` sends all failed fields directly to the LLM to fetch content.

    All final content is saved to the ARTICLES table, and validated XPaths are stored in TRACKING_DOMAINS.
    Only the 5 most recent XPaths are used, making the system self-healing and updating.

Helper files include:

    LLM_XPATH_GENERATION.py (LLM prompts for fetching XPaths)
    keyword_matcher.py (logic for keyword matching)
    Create_Tracking_Domains_Database.py and Create_Articles_Database.py (database schemas)
    batch_scraper.py (runs multiple articles sequentially)

Helper functions in main_scraper.py include:

    extract_datetime_from_elements() - Extract datetime from XPath
    extract_content_with_xpaths() - Extract content using XPath
    validate_extracted_fields() - Validate extracted data per defined conditions



TL:DR;-
Set these and rename env to .env

        OPENAI_API_KEY = ""
        TOTAL_LLM_CALLS='0'(will auto-update no need to touch, unless want to reset)

In Main_Scraper.py

        MAX_RETRIES = 3 (Max amount of times LLM is called in case base XPATHS fail)
        ENABLE_DIRECT_LLM_FALLBACK = True (Set hard-fallback in case XPATHS fail)

Adjust Prompt/LLM settings in LLM_XPATH_GENERATION.py -
           
        response_ai = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": cleaned_html}
            ],
            temperature=0.3
        )

        (Adjust all three prompt calls in generate_initial_xpaths(), retry_failed_xpaths(), direct_llm_extraction())


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



Fututre Updates-

1)Add a new table to track where the Hard_LLM call is being needed, upon observation it is mostly in author names, since different websites have different bylines, including some bundling it together with the byline without any different css/selector for it.
Then store those domains/links/category to a new table to understand where model is failing and improve cost furhter.

2) Improve Validation Algorithm, to check for title, content etc.

3) Improve the XPATH fetching algorithm, currently it is the most recent 5 XPATHS that work, change it so that each XPATH now has a confidence rating that increases when it succesfully validates, also to check whether validated content is correct or not, since sometimes despite validation outputs are broken.



