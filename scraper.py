import httpx
from bs4 import BeautifulSoup
import re
import hashlib
from datetime import datetime
from database import add_job, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def scrape_unjobs():
    jobs = []
    try:
        with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=30) as client:
            resp = client.get("https://unjobs.org/")
            if resp.status_code != 200:
                print(f"unjobs.org returned {resp.status_code}")
                return jobs
            
            soup = BeautifulSoup(resp.text, "lxml")
            
            for link in soup.find_all("a", href=re.compile(r"/vacancies/")):
                title = link.get_text(strip=True)
                url = link["href"]
                if not url.startswith("http"):
                    url = "https://unjobs.org" + url
                
                org_text = ""
                parent = link.parent
                if parent:
                    for sibling in link.next_siblings:
                        text = getattr(sibling, 'get_text', lambda **kw: str(sibling))(strip=True) if hasattr(sibling, 'get_text') else str(sibling).strip()
                        if text and len(text) > 2:
                            org_text = text
                            break
                
                location = ""
                if "," in title:
                    parts = title.rsplit(",", 1)
                    if len(parts) == 2 and len(parts[1].strip()) < 50:
                        location = parts[1].strip()
                
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
    jobs = []
    try:
        with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=30) as client:
            resp = client.get("https://www.impactpool.org/search")
            if resp.status_code != 200:
                print(f"impactpool.org returned {resp.status_code}")
                return jobs
            
            soup = BeautifulSoup(resp.text, "lxml")
            links = soup.find_all("a", href=lambda h: h and "/jobs/" in h)
            for link in links:
                title_div = link.find("div", attrs={"type": "cardTitle"})
                if not title_div: continue
                title = title_div.get_text(strip=True)
                
                url = link["href"]
                if not url.startswith("http"):
                    url = "https://www.impactpool.org" + url
                
                body_divs = link.find_all("div", attrs={"type": "bodyEmphasis"})
                org = body_divs[0].get_text(strip=True) if len(body_divs) > 0 else ""
                loc = body_divs[1].get_text(strip=True) if len(body_divs) > 1 else ""
                
                grade = ""
                grade_match = re.search(r'\b(P-?[1-5]|D-?[1-2]|G-?[1-7]|NO-?[A-D]|SC-?[1-9])\b', title, re.IGNORECASE)
                if grade_match:
                    grade = grade_match.group(1).upper()
                
                job_id = hashlib.md5(url.encode()).hexdigest()
                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "organization": org,
                    "location": loc,
                    "url": url,
                    "grade": grade,
                    "source": "Impactpool"
                })
    except Exception as e:
        print(f"Error scraping impactpool.org: {e}")
    return jobs

def scrape_linkedin():
    jobs = []
    try:
        with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=30) as client:
            resp = client.get("https://www.linkedin.com/jobs/search?keywords=united%20nations&location=Worldwide")
            if resp.status_code != 200:
                print(f"linkedin returned {resp.status_code}")
                return jobs
            
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.find_all("div", class_="base-card")
            for card in cards:
                title_elem = card.find("h3")
                if not title_elem: continue
                title = title_elem.get_text(strip=True)
                
                link = card.find("a", class_="base-card__full-link")
                if not link: continue
                url = link["href"]
                
                org_elem = card.find("h4")
                org = org_elem.get_text(strip=True) if org_elem else ""
                
                loc_elem = card.find("span", class_="job-search-card__location")
                loc = loc_elem.get_text(strip=True) if loc_elem else ""
                
                grade = ""
                grade_match = re.search(r'\b(P-?[1-5]|D-?[1-2]|G-?[1-7]|NO-?[A-D]|SC-?[1-9])\b', title, re.IGNORECASE)
                if grade_match:
                    grade = grade_match.group(1).upper()
                
                url_clean = url.split("?")[0]
                job_id = hashlib.md5(url_clean.encode()).hexdigest()
                
                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "organization": org,
                    "location": loc,
                    "url": url_clean,
                    "grade": grade,
                    "source": "LinkedIn"
                })
    except Exception as e:
        print(f"Error scraping linkedin: {e}")
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
    
    print("Scraping LinkedIn...")
    linkedin = scrape_linkedin()
    all_jobs.extend(linkedin)
    print(f"  Found {len(linkedin)} jobs")
    
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
