INSERT INTO feed_sources (name, url, category, language, active) VALUES

-- World News (10)
('BBC News - World',         'http://feeds.bbci.co.uk/news/world/rss.xml',               'world',      'en', TRUE),
('Reuters - World News',     'https://feeds.reuters.com/reuters/worldnews',               'world',      'en', TRUE),
('Al Jazeera - News',        'https://www.aljazeera.com/xml/rss/all.xml',                'world',      'en', TRUE),
('AP News - Top Headlines',  'https://feeds.apnews.com/rss/apf-topnews',                 'world',      'en', TRUE),
('The Guardian - World',     'https://www.theguardian.com/world/rss',                    'world',      'en', TRUE),
('BBC News - Top Stories',   'http://feeds.bbci.co.uk/news/rss.xml',                     'world',      'en', TRUE),
('Reuters - Top News',       'https://feeds.reuters.com/reuters/topnews',                'world',      'en', TRUE),
('AP News - World News',     'https://feeds.apnews.com/rss/apf-WorldNews',               'world',      'en', TRUE),
('The Guardian - US News',   'https://www.theguardian.com/us-news/rss',                  'world',      'en', TRUE),
('Al Jazeera - Features',    'https://www.aljazeera.com/xml/rss/sport.xml',              'world',      'en', TRUE),

-- Technology (10)
('TechCrunch',               'https://techcrunch.com/feed/',                             'technology', 'en', TRUE),
('Ars Technica',             'http://feeds.arstechnica.com/arstechnica/index',           'technology', 'en', TRUE),
('Wired',                    'https://www.wired.com/feed/rss',                           'technology', 'en', TRUE),
('The Verge',                'https://www.theverge.com/rss/index.xml',                   'technology', 'en', TRUE),
('Hacker News - Front Page', 'https://hnrss.org/frontpage',                              'technology', 'en', TRUE),
('TechCrunch - Startups',    'https://techcrunch.com/category/startups/feed/',           'technology', 'en', TRUE),
('Ars Technica - Tech',      'http://feeds.arstechnica.com/arstechnica/technology-lab',  'technology', 'en', TRUE),
('MIT Technology Review',    'https://www.technologyreview.com/feed/',                   'technology', 'en', TRUE),
('Engadget',                 'https://www.engadget.com/rss.xml',                         'technology', 'en', TRUE),
('Hacker News - Best',       'https://hnrss.org/best',                                   'technology', 'en', TRUE),

-- Business (8)
('Reuters - Business',       'https://feeds.reuters.com/reuters/businessnews',           'business',   'en', TRUE),
('BBC News - Business',      'http://feeds.bbci.co.uk/news/business/rss.xml',            'business',   'en', TRUE),
('Financial Times',          'https://www.ft.com/news-feed?format=rss',                  'business',   'en', TRUE),
('Fortune',                  'https://fortune.com/feed/',                                 'business',   'en', TRUE),
('Bloomberg Markets',        'https://feeds.bloomberg.com/markets/news.rss',             'business',   'en', TRUE),
('CNBC - Business News',     'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147', 'business', 'en', TRUE),
('The Economist',            'https://www.economist.com/finance-and-economics/rss.xml',  'business',   'en', TRUE),
('MarketWatch',              'https://feeds.marketwatch.com/marketwatch/topstories/',    'business',   'en', TRUE),

-- Science (5)
('NASA Breaking News',       'https://www.nasa.gov/rss/dyn/breaking_news.rss',           'science',    'en', TRUE),
('New Scientist',            'https://www.newscientist.com/feed/home',                   'science',    'en', TRUE),
('Scientific American',      'http://rss.sciam.com/ScientificAmerican-Global',           'science',    'en', TRUE),
('Nature News',              'https://www.nature.com/nature.rss',                        'science',    'en', TRUE),
('Science Daily',            'https://www.sciencedaily.com/rss/top/science.xml',         'science',    'en', TRUE),

-- Sports (5)
('BBC Sport',                'http://feeds.bbci.co.uk/sport/rss.xml',                   'sports',     'en', TRUE),
('ESPN',                     'https://www.espn.com/espn/rss/news',                       'sports',     'en', TRUE),
('Reuters - Sports',         'https://feeds.reuters.com/reuters/sportsNews',             'sports',     'en', TRUE),
('Sky Sports',               'https://www.skysports.com/rss/12040',                      'sports',     'en', TRUE),
('CBS Sports',               'https://www.cbssports.com/rss/headlines/',                 'sports',     'en', TRUE),

-- Health (5)
('WHO News',                 'https://www.who.int/rss-feeds/news-english.xml',           'health',     'en', TRUE),
('WebMD Health',             'https://rssfeeds.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC', 'health', 'en', TRUE),
('Healthline',               'https://www.healthline.com/rss/nutrition',                 'health',     'en', TRUE),
('CDC Newsroom',             'https://tools.cdc.gov/api/v2/resources/media/132608.rss',  'health',     'en', TRUE),
('MedlinePlus Health News',  'https://medlineplus.gov/xml/mplus_topics.xml',             'health',     'en', TRUE),

-- India News (7)
('Times of India - Top',     'https://timesofindia.indiatimes.com/rssfeedstopstories.cms',         'india', 'en', TRUE),
('NDTV News',                'https://feeds.feedburner.com/ndtvnews-top-stories',                  'india', 'en', TRUE),
('The Hindu',                'https://www.thehindu.com/news/national/feeder/default.rss',          'india', 'en', TRUE),
('Hindustan Times',          'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',    'india', 'en', TRUE),
('Indian Express',           'https://indianexpress.com/feed/',                                    'india', 'en', TRUE),
('Economic Times - India',   'https://economictimes.indiatimes.com/rssfeedstopstories.cms',        'india', 'en', TRUE),
('Deccan Herald',            'https://www.deccanherald.com/rss-feed/india.rss',                    'india', 'en', TRUE)

ON CONFLICT (url) DO NOTHING;
