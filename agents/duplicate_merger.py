import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class DuplicateMerger:
    """Identifies and clusters highly similar news articles using TF-IDF and Cosine Similarity."""

    def find_clusters(self, db_conn):
        """
        Fetches 'new' articles from the last 6 hours and clusters them if similarity >= 0.80.
        Returns a list of clusters, where each cluster is a list of article IDs.
        """
        six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)
        
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, full_text FROM articles "
                "WHERE status = 'new' AND created_at >= %s",
                (six_hours_ago,)
            )
            articles = cur.fetchall()

        if not articles:
            return []

        ids = [a["id"] for a in articles]
        texts = [str(a["full_text"]) if a["full_text"] else "" for a in articles]

        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
        except ValueError:
            # Handles edge case where all texts are empty or consist only of stop words
            return [[article_id] for article_id in ids]

        sim_matrix = cosine_similarity(tfidf_matrix)

        visited = set()
        clusters = []

        # Simple greedy grouping based on similarity threshold
        for i in range(len(ids)):
            if i in visited:
                continue
            
            cluster = [ids[i]]
            visited.add(i)

            for j in range(i + 1, len(ids)):
                if j not in visited and sim_matrix[i][j] >= 0.80:
                    cluster.append(ids[j])
                    visited.add(j)

            clusters.append(cluster)

        return clusters

    def merge_cluster(self, cluster_article_ids, db_conn):
        """
        Takes a list of IDs, makes the one with the highest viral_score the primary,
        marks the rest as 'merged', and logs it to `story_clusters`.
        """
        if len(cluster_article_ids) < 2:
            return cluster_article_ids[0] if cluster_article_ids else None

        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            placeholders = ','.join(['%s'] * len(cluster_article_ids))
            cur.execute(
                f"SELECT id, viral_score FROM articles WHERE id IN ({placeholders})",
                tuple(cluster_article_ids)
            )
            articles = cur.fetchall()

        # Sort descending by viral_score, then tie-break by ID
        sorted_articles = sorted(articles, key=lambda x: (x["viral_score"] or 0, x["id"]), reverse=True)
        primary_id = sorted_articles[0]["id"]
        member_ids = [a["id"] for a in sorted_articles if a["id"] != primary_id]
        member_ids_str = ",".join(map(str, member_ids))

        # We will use the transaction block to secure DB updates
        with db_conn:
            with db_conn.cursor() as cur:
                # Update merged duplicate articles
                member_placeholders = ','.join(['%s'] * len(member_ids))
                cur.execute(
                    f"UPDATE articles SET status = 'merged', merged_from = %s, cluster_id = %s "
                    f"WHERE id IN ({member_placeholders})",
                    (str(primary_id), primary_id, *member_ids)
                )

                # Update the primary article's cluster_id (it remains status='new' or previous status)
                cur.execute(
                    "UPDATE articles SET cluster_id = %s WHERE id = %s",
                    (primary_id, primary_id)
                )

                # Assuming similarity is at least 0.80 based on the clustering threshold
                cur.execute(
                    "INSERT INTO story_clusters (primary_article_id, member_article_ids, similarity_score) "
                    "VALUES (%s, %s, %s)",
                    (primary_id, member_ids_str, 0.80)
                )

        return primary_id

    def run(self, db_conn):
        """
        Runs the full cluster finding and merging pipeline.
        Returns the number of clusters successfully merged.
        """
        clusters = self.find_clusters(db_conn)
        merges_performed = 0

        for cluster in clusters:
            if len(cluster) > 1:
                self.merge_cluster(cluster, db_conn)
                merges_performed += 1

        return merges_performed

if __name__ == "__main__":
    # Test stub structure
    import os
    conn_string = os.getenv("DATABASE_URL", "host=localhost port=5432 dbname=news_system user=postgres")
    try:
        conn = psycopg2.connect(conn_string)
        merger = DuplicateMerger()
        merge_count = merger.run(conn)
        print(f"DuplicateMerger run complete. Merged {merge_count} story clusters.")
        conn.close()
    except Exception as e:
        print(f"Error executing DuplicateMerger: {e}")
