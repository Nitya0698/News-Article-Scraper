"""
Database Setup Script - Creates the database and tables
"""
import sqlite3

# Connect to database (creates it if it doesn't exist)
conn = sqlite3.connect('articles.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS TRACKING_DOMAINS (
        Domain TEXT PRIMARY KEY,
        TotalFailures INTEGER DEFAULT 0,
        AuthorXPath TEXT,
        TitleXPath TEXT,
        DateXPath TEXT,
        TimeXPath TEXT,
        ContentXPath TEXT,
        LastUpdated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

print("XPATHS table created successfully!")

# Second table will be added here later

# Commit changes and close connection
conn.commit()
conn.close()

print("Database setup complete!")