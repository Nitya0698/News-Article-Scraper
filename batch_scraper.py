import subprocess
import sys
import time
from datetime import datetime
import argparse


def read_urls_from_file(file_path):
    """
    Read URLs from a text file (one URL per line).
    
    Args:
        file_path (str): Path to the text file
    
    Returns:
        list: List of URLs (empty lines and comments are filtered out)
    """
    urls = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                # Skip empty lines and comments
                if url and not url.startswith('#'):
                    urls.append(url)
        
        return urls
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found!")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)


def batch_scrape(input_file, scraper_script="main_scraper.py", delay=2, log_file=None):
    """
    Scrape multiple URLs by calling main_scraper.py for each URL.
    
    Args:
        input_file (str): Path to file containing URLs
        scraper_script (str): Path to main_scraper.py
        delay (int): Delay in seconds between requests
        log_file (str): Optional path to log file for results
    """
    
    # Read URLs
    urls = read_urls_from_file(input_file)
    total_urls = len(urls)
    
    if total_urls == 0:
        print("No URLs found in the file!")
        return
    
    print(f"\n{'='*60}")
    print(f"BATCH SCRAPER")
    print(f"{'='*60}")
    print(f"Total URLs to process: {total_urls}")
    print(f"Scraper script: {scraper_script}")
    print(f"Delay between requests: {delay}s")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Track results
    successful = []
    failed = []
    
    # Process each URL
    for idx, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{total_urls}] Processing: {url}")
        print(f"{'='*60}")
        
        try:
            # Call main_scraper.py with URL piped to stdin
            result = subprocess.run(
                ['python3', scraper_script],
                input=url + '\n',
                text=True,
                capture_output=False,  # Show output in real-time
                timeout=60  # 60 second timeout per URL
            )
            
            if result.returncode == 0:
                successful.append(url)
                print(f"\n[{idx}/{total_urls}] Successfully processed!")
            else:
                failed.append({'url': url, 'error': f'Script exited with code {result.returncode}'})
                print(f"\n[{idx}/{total_urls}] Failed with exit code {result.returncode}")
        
        except subprocess.TimeoutExpired:
            failed.append({'url': url, 'error': 'Timeout (60s)'})
            print(f"\n[{idx}/{total_urls}] Timeout - took longer than 60 seconds")
        
        except Exception as e:
            failed.append({'url': url, 'error': str(e)})
            print(f"\n[{idx}/{total_urls}] Error: {str(e)}")
        
        # Add delay between requests (except for last one)
        if idx < total_urls:
            print(f"\nWaiting {delay}s before next request...")
            time.sleep(delay)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"BATCH SCRAPING COMPLETED")
    print(f"{'='*60}")
    print(f"Total URLs processed: {total_urls}")
    print(f"✓ Successful: {len(successful)}")
    print(f"✗ Failed: {len(failed)}")
    print(f"Success rate: {(len(successful)/total_urls*100):.1f}%")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Show failed URLs if any
    if failed:
        print("\nFailed URLs:")
        for fail in failed:
            print(f"{fail['url']}")
            print(f"Error: {fail['error']}\n")
    
    # Write log file if specified
    if log_file:
        write_log(successful, failed, log_file, total_urls)


def write_log(successful, failed, log_file, total_urls):
    """Write scraping results to a log file."""
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"Batch Scraping Log\n")
            f.write(f"{'='*60}\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total URLs: {total_urls}\n")
            f.write(f"Successful: {len(successful)}\n")
            f.write(f"Failed: {len(failed)}\n")
            f.write(f"{'='*60}\n\n")
            
            f.write(f"SUCCESSFUL ({len(successful)})\n")
            f.write(f"{'-'*60}\n")
            for url in successful:
                f.write(f"{url}\n")
            
            f.write(f"\n\nFAILED ({len(failed)})\n")
            f.write(f"{'-'*60}\n")
            for fail in failed:
                f.write(f"URL: {fail['url']}\n")
                f.write(f"Error: {fail['error']}\n\n")
        
        print(f"✓ Log file saved: {log_file}")
    
    except Exception as e:
        print(f"✗ Could not write log file: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Batch scrape articles by calling main_scraper.py for each URL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_scraper.py urls.txt
  python batch_scraper.py urls.txt --delay 3
  python batch_scraper.py urls.txt --scraper /path/to/main_scraper.py --delay 5
  python batch_scraper.py urls.txt --delay 3 --log results.log
  
Input file format (urls.txt):
  https://example.com/article1
  https://example.com/article2
  # This is a comment (will be ignored)
  https://example.com/article3
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Path to text file containing URLs (one per line)'
    )
    
    parser.add_argument(
        '--scraper',
        type=str,
        default='main_scraper.py',
        help='Path to main_scraper.py (default: main_scraper.py in current directory)'
    )
    
    parser.add_argument(
        '--delay',
        type=int,
        default=0,
        help='Delay in seconds between requests (default: 0)'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        help='Path to log file for results (optional)'
    )
    
    args = parser.parse_args()
    
    # Run batch scraper
    batch_scrape(args.input_file, scraper_script=args.scraper, delay=args.delay, log_file=args.log)