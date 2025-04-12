import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import json
import os
import re

class FinancialNewsScraper:
    def __init__(self, sources_config):
        self.sources = sources_config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Create directory for storing scraped articles
        os.makedirs('scraped_mf', exist_ok=True)
    
    def scrape_all_sources(self, limit_per_source=10):
        """Scrape articles from all configured sources"""
        all_articles = []
        
        for source_name, source_config in self.sources.items():
            print(f"Scraping from {source_name}...")
            try:
                articles = self.scrape_source(source_name, source_config, limit_per_source)
                all_articles.extend(articles)
                
                # Save articles from this source
                self._save_articles(articles, source_name)
                
                # Respect the site by waiting between sources
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                print(f"Error scraping {source_name}: {str(e)}")
        
        return all_articles
    
    def scrape_source(self, source_name, source_config, limit):
        """Scrape articles from a specific source"""
        articles = []
        
        # Get URLs from the source's main page
        main_url = source_config['main_url']
        article_links = self._get_article_links(main_url, source_config)
        
        # Limit the number of articles to process
        article_links = article_links[:limit]
        
        # Process each article
        for url in article_links:
            try:
                article = self._parse_article(url, source_name, source_config)
                if article:
                    articles.append(article)
                
                # Be nice to the website
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                print(f"Error parsing article {url}: {str(e)}")
        
        return articles
    
    def _get_article_links(self, main_url, source_config):
        """Extract article links from the main page"""
        response = requests.get(main_url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        link_patterns = source_config.get('link_patterns', [])
        
        # Extract links based on patterns specific to the source
        for pattern in link_patterns:
            elements = soup.select(pattern)
            for element in elements:
                if element.has_attr('href'):
                    link = element['href']
                    # Handle relative URLs
                    if link.startswith('/'):
                        if not main_url.endswith('/'):
                            link = main_url + link
                        else:
                            link = main_url[:-1] + link
                    # Handle protocol-relative URLs
                    elif link.startswith('//'):
                        link = 'https:' + link
                    # Handle URLs without domain
                    elif not link.startswith('http'):
                        domain = self._extract_domain(main_url)
                        link = domain + link
                        
                    links.append(link)
        
        # Remove duplicates while preserving order
        unique_links = []
        for link in links:
            if link not in unique_links and self._is_valid_article_url(link, source_config):
                unique_links.append(link)
        
        return unique_links
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        match = re.match(r'(https?://[^/]+)', url)
        if match:
            return match.group(1)
        return url
    
    def _is_valid_article_url(self, url, source_config):
        """Check if URL is a valid article URL"""
        # Skip URLs with certain patterns
        exclude_patterns = source_config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if pattern in url:
                return False
                
        # Skip non-article pages like category pages
        if any(term in url for term in ['/tag/', '/category/', '/author/', '/about/', '/contact/']):
            return False
            
        return True
    
    def _parse_article(self, url, source_name, source_config):
        """Parse a single article using BeautifulSoup"""
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract article components based on source-specific selectors
            article_selectors = source_config.get('article_selectors', {})
            
            # Title
            title = self._extract_element_text(soup, article_selectors.get('title', 'h1'))
            
            # Content
            content = self._extract_article_content(soup, article_selectors.get('content', 'article'))
            
            # Skip articles with little content
            if not title or not content or len(content.split()) < 50:
                return None
            
            # Extract date
            publish_date = self._extract_publish_date(soup, article_selectors.get('date', None))
            
            # Extract authors
            authors = self._extract_authors(soup, article_selectors.get('authors', None))
            
            # Extract metadata
            data = {
                'title': title,
                'text': content,
                'url': url,
                'source': source_name,
                'authors': authors,
                'publish_date': publish_date,
                'scraped_date': datetime.now().isoformat()
            }
            
            return data
        except Exception as e:
            print(f"Error downloading/parsing {url}: {str(e)}")
            return None
    
    def _extract_element_text(self, soup, selector):
        """Extract text from an element"""
        if not selector:
            return ""
            
        element = soup.select_one(selector)
        if element:
            return element.get_text().strip()
        return ""
    
    def _extract_article_content(self, soup, content_selector):
        """Extract and clean article content"""
        content_elements = soup.select(content_selector)
        if not content_elements:
            # Fallback to paragraph extraction
            content_elements = soup.select('article p, .article-body p, .story-content p, .article-content p')
        
        # Extract text from all content elements
        content = []
        for element in content_elements:
            # Skip elements likely to be not part of the main content
            if element.parent and element.parent.name in ['nav', 'header', 'footer', 'aside']:
                continue
            
            # Skip elements with certain classes
            classes = element.get('class', [])
            if any(c in str(classes).lower() for c in ['caption', 'sidebar', 'related', 'footer', 'comment']):
                continue
                
            # Clean text and add to content
            text = element.get_text().strip()
            if text and len(text) > 20:  # Skip very short paragraphs
                content.append(text)
        
        return "\n\n".join(content)
    
    def _extract_publish_date(self, soup, date_selector):
        """Extract publication date"""
        if not date_selector:
            # Try common patterns for dates
            date_selectors = [
                'time', 
                '.date', 
                '.published', 
                'meta[property="article:published_time"]', 
                'meta[name="date"]'
            ]
            
            for selector in date_selectors:
                element = soup.select_one(selector)
                if element:
                    if element.name == 'meta':
                        date_str = element.get('content')
                    else:
                        date_str = element.get('datetime', element.get_text())
                    
                    # Try to parse the date
                    try:
                        date_obj = self._parse_date_string(date_str)
                        if date_obj:
                            return date_obj.isoformat()
                    except:
                        continue
        else:
            element = soup.select_one(date_selector)
            if element:
                date_str = element.get('datetime', element.get_text())
                try:
                    date_obj = self._parse_date_string(date_str)
                    if date_obj:
                        return date_obj.isoformat()
                except:
                    pass
        
        # No date found
        return None
    
    def _parse_date_string(self, date_str):
        """Try to parse date string in various formats"""
        if not date_str:
            return None
            
        date_str = date_str.strip()
        
        # ISO format
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass
        
        # Try common formats
        formats = [
            '%Y-%m-%d', 
            '%Y-%m-%dT%H:%M:%S', 
            '%Y-%m-%d %H:%M:%S',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d/%m/%Y',
            '%m/%d/%Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
                
        return None
    
    def _extract_authors(self, soup, authors_selector):
        """Extract authors from article"""
        authors = []
        
        if not authors_selector:
            # Try common patterns for authors
            author_selectors = [
                '.author', 
                '.byline', 
                'meta[name="author"]',
                'a[rel="author"]'
            ]
            
            for selector in author_selectors:
                elements = soup.select(selector)
                for element in elements:
                    if element.name == 'meta':
                        author = element.get('content', '').strip()
                    else:
                        author = element.get_text().strip()
                        
                    if author and len(author) < 100 and author not in authors:  # Avoid picking up non-author text
                        authors.append(author)
        else:
            elements = soup.select(authors_selector)
            for element in elements:
                author = element.get_text().strip()
                if author and author not in authors:
                    authors.append(author)
        
        # Clean up author names
        cleaned_authors = []
        for author in authors:
            # Remove "By" prefix
            author = re.sub(r'^[Bb][Yy][\s:]+', '', author)
            # Remove "Author:" prefix
            author = re.sub(r'^[Aa]uthor[\s:]+', '', author)
            author = author.strip()
            if author and author not in cleaned_authors:
                cleaned_authors.append(author)
                
        return cleaned_authors
    
    def _save_articles(self, articles, source_name):
        """Save articles to JSON file"""
        if not articles:
            return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"scraped_mf/{source_name}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        print(f"Saved {len(articles)} articles from {source_name} to {filename}")
        

# SOURCES_CONFIG = {
#     'RELIANCE': {
#         'main_url': 'https://www.cnbctv18.com/market/stocks/reliance-industries-share-price/RI/',
#         'link_patterns': ['.Card-title a', '.Card-titleContainer a'],
#         'article_selectors': {
#             'title': '.ArticleHeader-headline',
#             'content': '.ArticleBody-articleBody p',
#             'date': 'time',
#             'authors': '.Author-authorName'
#         },
#         'exclude_patterns': ['/video/', '/live-updates/']
#     }
# }

# SOURCES_CONFIG = {
#     'ICICI': {
#         'main_url': 'https://finance.yahoo.com/quote/0P0000XWAB.BO/',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'HDFCBANK': {
#         'main_url': 'https://finance.yahoo.com/quote/HDFCBANK.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'TCS': {
#         'main_url': 'https://finance.yahoo.com/quote/TCS.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'BHARTIARTL': {
#         'main_url': 'https://finance.yahoo.com/quote/BHARTIARTL.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'ICICIBANK': {
#         'main_url': 'https://finance.yahoo.com/quote/ICICIBANK.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'SBIN': {
#         'main_url': 'https://finance.yahoo.com/quote/SBIN.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'INFY': {
#         'main_url': 'https://finance.yahoo.com/quote/INFY.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'HINDUNILVR': {
#         'main_url': 'https://finance.yahoo.com/quote/HINDUNILVR.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'BAJFINANCE': {
#         'main_url': 'https://finance.yahoo.com/quote/BAJFINANCE.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'ITC': {
#         'main_url': 'https://finance.yahoo.com/quote/ITC.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'LICI': {
#         'main_url': 'https://finance.yahoo.com/quote/LICI.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'LT': {
#         'main_url': 'https://finance.yahoo.com/quote/LT.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'KOTAKBANK': {
#         'main_url': 'https://finance.yahoo.com/quote/KOTAKBANK.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'SUNPHARMA': {
#         'main_url': 'https://finance.yahoo.com/quote/SUNPHARMA.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'HCLTECH': {
#         'main_url': 'https://finance.yahoo.com/quote/HCLTECH.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'MARUTI': {
#         'main_url': 'https://finance.yahoo.com/quote/MARUTI.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'NTPC': {
#         'main_url': 'https://finance.yahoo.com/quote/NTPC.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'ULTRACEMCO': {
#         'main_url': 'https://finance.yahoo.com/quote/ULTRACEMCO.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'AXISBANK': {
#         'main_url': 'https://finance.yahoo.com/quote/AXISBANK.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     },
#     'M&M': {
#         'main_url': 'https://finance.yahoo.com/quote/M&M.NS/news',
#         'link_patterns': ['a.subtle-link'],
#         'article_selectors': {
#             'title': 'h1',
#             'content': 'div.caas-body',
#             'date': 'time',
#             'authors': 'div.caas-attr-provider'
#         },
#         'exclude_patterns': ['/video', '/promo/', '/subscribe/']
#     }
# }


SOURCES_CONFIG = {
    'INF109K012K1': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000XWAB.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF754K01LO0': {
        'main_url': 'https://finance.yahoo.com/quote/0P0001KBFU.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF179K01VQ4': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000XWHN0.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF204K01XZ7': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000Y3TV5.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF174KA1IL2': {
        'main_url': 'https://finance.yahoo.com/quote/0P0001K6M13.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF879O01027': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000YW4J6.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF109K01Q49': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000YTAH6.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF179KB1HT1': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000Z5JK1.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF754K01NY5': {
        'main_url': 'https://finance.yahoo.com/quote/0P0001KBFV.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF209K01UU3': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000XZ2P1.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF109K016L0': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000XWAT.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF209K01UR9': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000XZXH1.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF740K01OK1': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000Y5D78.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF200K01UM9': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000XURX6.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    },
    'INF194KB1BV1': {
        'main_url': 'https://finance.yahoo.com/quote/0P0000Y4H28.BO/news/',
        'link_patterns': ['a.subtle-link'],
        'article_selectors': {
            'title': 'h1',
            'content': 'div.caas-body',
            'date': 'time',
            'authors': 'div.caas-attr-provider'
        },
        'exclude_patterns': ['/video', '/promo/', '/subscribe/']
    }
}
def run_scraper():
    scraper = FinancialNewsScraper(SOURCES_CONFIG)
    articles = scraper.scrape_all_sources(limit_per_source=5)
    print(f"Total articles scraped: {len(articles)}")
    return articles

if __name__ == "__main__":
    run_scraper()
    
    
    