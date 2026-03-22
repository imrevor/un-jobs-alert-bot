import requests
from bs4 import BeautifulSoup
import re
import hashlib
from datetime import datetime
from database import add_job, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def scrape_unjobs():
    """Scrape latest jobs from unjobs.org homepage"""
    jobs = []
    try:
        resp = requests.get("https://unjobs.org/", headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"unjobs.org returned {resp.status_code}")
            return jobs
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Parse job listings from the homepage
        for link in soup.find_all("a", href=re.compile(r"/vacancies/")):
            title = link.get_text(strip=True)
            url = link["href"]
            if not url.startswith("http"):
                url = "https://unjobs.org" + url
            
            # Get organization (next sibling text)
            org_text = ""
            parent = link.parent
            if parent:
                # Organization is typically in text after the link
                for sibling in link.next_siblings:
                    text = getattr(sibling, 'get_text', lambda **kw: str(sibling))(strip=True) if hasattr(sibling, 'get_text') else str(sibling).strip()
                    if text and len(text) > 2:
                        org_text = text
                        break
            
            # Extract location from title (usually "Title, Location")
            location = ""
            if "," in title:
                parts = title.rsplit(",", 1)
                if len(parts) == 2 and len(parts[1].strip()) < 50:
                    location = parts[1].strip()
            
            # Extract grade from title
            grade = ""
            grade_match = re.search(r'\b(P-?[1-5]|D-?[1-2]|G-?[1-7]|NO-?[A-D]|SC-?[1-9])\b', title, re.IGNORECASE)
            if grade_match:
                grade = grade_match.group(1).upper()
            
            job_id = hashlib.md5(url.encode()).hexdigest()
            
            jobs.append({
                "job_id": job_id,
                "title": title,
                "organization": org_text,
                "location": location,
                "url": url,
                "grade": grade,
                "source": "unjobs"
            })
    
    except Exception as e:
        print(f"Error scraping unjobs.org: {e}")
    
    return jobs

def scrape_impactpool():
    """Scrape latest jobs from impactpool.org"""
    jobs = []
    try:
        resp = requests.get("https://www.impactpool.org/jobs", headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"impactpool.org returned {resp.status_code}")
            return jobs
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        for card in soup.find_all("a", href=re.compile(r"/jobs/")):
            title = card.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            url = card["href"]
            if not url.startswith("http"):
                url = "https://www.impactpool.org" + url
            
            location = ""
            grade = ""
            org = ""
            
            grade_match = re.search(r'\b(P-?[1-5]|D-?[1-2])\b', title, re.IGNORECASE)
            if grade_match:
                grade = grade_match.group(1).upper()
            
            if "," in title:
                parts = title.rsplit(",", 1)
                if len(parts) == 2 and len(parts[1].strip()) < 50:
                    location = parts[1].strip()
            
            job_id = hashlib.md5(url.encode()).hexdigest()
            
            jobs.append({
                "job_id": job_id,
                "title": title,
                "organization": org,
                "location": location,
                "url": url,
                "grade": grade,
                "source": "impactpool"
            })
    
    except Exception as e:
        print(f"Error scraping impactpool.org: {e}")
    
    return jobs

def run_scraper():
    """Run all scrapers and store results"""
    init_db()
    
    all_jobs = []
    
    print("Scraping unjobs.org...")
    unjobs = scrape_unjobs()
    all_jobs.extend(unjobs)
    print(f"  Found {len(unjobs)} jobs")
    
    print("Scraping impactpool.org...")
    impact = scrape_impactpool()
    all_jobs.extend(impact)
    print(f"  Found {len(impact)} jobs")
    
    # Store in database
    new_count = 0
    for job in all_jobs:
        try:
            add_job(
                job_id=job["job_id"],
                title=job["title"],
                organization=job["organization"],
                location=job["location"],
                url=job["url"],
                grade=job["grade"],
                source=job["source"]
            )
            new_count += 1
        except Exception as e:
            pass  # Duplicate, skip
    
    print(f"Total scraped: {len(all_jobs)}, stored: {new_count}")
    return all_jobs

if __name__ == "__main__":
    run_scraper()
