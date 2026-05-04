INSERT INTO feed_sources (name, url, category, active) VALUES
('BBC World', 'http://feeds.bbci.co.uk/news/world/rss.xml', 'world', true),
('BBC Tech', 'http://feeds.bbci.co.uk/news/technology/rss.xml', 'technology', true),
('Reuters Top', 'https://feeds.reuters.com/reuters/topNews', 'world', true),
('Reuters Biz', 'https://feeds.reuters.com/reuters/businessNews', 'business', true),
('Al Jazeera', 'https://www.aljazeera.com/xml/rss/all.xml', 'world', true),
('TechCrunch', 'https://techcrunch.com/feed/', 'technology', true),
('ESPN', 'https://www.espn.com/espn/rss/news', 'sports', true),
('CNN Top', 'http://rss.cnn.com/rss/edition.rss', 'world', true),
('Guardian World', 'https://www.theguardian.com/world/rss', 'world', true),
('NDTV India', 'https://feeds.feedburner.com/ndtvnews-top-stories', 'india', true),
('Wired', 'https://www.wired.com/feed/rss', 'technology', true),
('Bloomberg', 'https://www.bloomberg.com/feed/podcast/decrypted.xml', 'business', true)
ON CONFLICT (url) DO UPDATE SET active=true;
