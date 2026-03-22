import datetime

class ViralScoreEngine:
    """Engine to estimate virality and breaking news probability for articles using deterministic rules."""
    
    def score(self, article_dict: dict) -> int:
        """Calculates a deterministic viral score from 0 to 100."""
        source_score_map = {
            "Reuters": 88, "AP": 87, "BBC": 85, "Guardian": 80,
            "TechCrunch": 75, "Wired": 72, "NDTV": 70, "Times of India": 68,
            "Hindustan Times": 65, "Economic Times": 70, "Indian Express": 68
        }
        source = article_dict.get("source")
        source_score = source_score_map.get(source, 35)

        pub_date = article_dict.get("published_date")
        if pub_date is None:
            recency_score = 15
        else:
            if isinstance(pub_date, str):
                try:
                    # Attempt to parse ISO format string
                    pub_date = datetime.datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except ValueError:
                    pass
            
            if isinstance(pub_date, datetime.datetime):
                # Ensure we have a timezone-aware comparison if possible
                now = datetime.datetime.now(pub_date.tzinfo)
                hours_diff = max(0, int((now - pub_date).total_seconds() / 3600))
                recency_score = max(0, 30 - (hours_diff * 3))
            else:
                recency_score = 15

        headline = article_dict.get("headline", "")
        headline_length = len(headline)
        if 60 <= headline_length <= 100:
            length_score = 15
        elif headline_length < 40:
            length_score = 5
        else:
            length_score = 10

        keywords = ["breaking", "exclusive", "first", "major", "crisis", "launch", "record", "ban", "crash", "surge"]
        headline_lower = headline.lower()
        keyword_score = min(20, sum(5 for kw in keywords if kw in headline_lower))

        total = source_score + recency_score + length_score + keyword_score
        return min(100, total)
        
    def is_breaking(self, headline: str) -> bool:
        """Returns True if the headline contains urgent keywords."""
        if not headline:
            return False
        urgent_words = ['breaking', 'urgent', 'alert', 'exclusive', 'live']
        return any(w in headline.lower() for w in urgent_words)
