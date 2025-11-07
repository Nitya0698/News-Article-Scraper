"""
Database Setup Script - Creates the database and tables
"""
import sqlite3

# Connect to database (creates it if it doesn't exist)
conn = sqlite3.connect('articles.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS ARTICLES (
        Domain TEXT,
        URL TEXT,
        Author TEXT,
        Time TEXT,
        Date TEXT,
        Title TEXT,
        Content TEXT,
        PRIMARY KEY (Domain, URL)
    )
''')

print("XPATHS table created successfully!")

# Second table will be added here later

# Commit changes and close connection
conn.commit()
conn.close()

print("Database setup complete!")