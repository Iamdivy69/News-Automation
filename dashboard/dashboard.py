import streamlit as st
import requests
import pandas as pd
import humanize
from datetime import datetime, timezone
import time

# --- Configuration ---
st.set_page_config(page_title="Autonomous News Dashboard", page_icon="📈", layout="wide")

API_BASE = "http://127.0.0.1:5000/api"

# --- API Functions (Cached) ---
@st.cache_data(ttl=60)
def fetch_articles(page=1, per_page=20, status='summarised', category=None, search=None):
    params = {'page': page, 'per_page': per_page, 'status': status}
    if category and category != 'All':
        params['category'] = category
    if search:
        params['search'] = search
    try:
        resp = requests.get(f"{API_BASE}/articles", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Failed to fetch articles: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_article_details(article_id):
    try:
        resp = requests.get(f"{API_BASE}/articles/{article_id}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Failed to fetch details for article {article_id}: {e}")
        return None

@st.cache_data(ttl=60)
def fetch_stats():
    try:
        resp = requests.get(f"{API_BASE}/stats", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Failed to fetch stats: {e}")
        return {}

def fetch_health():
    # Not cached so we can poll it live
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"postgresql": "error", "ollama": "error", "timestamp": "N/A", "error": str(e)}

# --- UI Helpers ---
def relative_time(iso_str):
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        return humanize.naturaltime(now - dt)
    except:
        return iso_str

# --- Pages ---
def page_feed():
    st.title("📰 Articles Feed")
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    search_term = st.sidebar.text_input("Search headlines...")
    
    stats = fetch_stats()
    status_options = ["summarised", "approved", "new", "merged", "needs_review"]
    status_counts = stats.get("articles_by_status", {}) if stats else {}
    
    status_display = [f"{s} ({status_counts.get(s, 0)} articles)" for s in status_options]
    status_selection = st.sidebar.selectbox("Status", status_display)
    status = status_selection.split(" (")[0]
    
    cat_opts = ["All"]
    cat_counts = stats.get("articles_by_category", {}) if stats else {}
    if cat_counts:
        cat_opts.extend(cat_counts.keys())
    
    total_articles = stats.get("total_articles", 0) if stats else 0
    cat_display = []
    for c in cat_opts:
        if c == "All":
            cat_display.append(f"All ({total_articles} articles)")
        else:
            cat_display.append(f"{c} ({cat_counts.get(c, 0)} articles)")
            
    category_selection = st.sidebar.selectbox("Category", cat_display)
    category = category_selection.split(" (")[0]
    
    # Pagination state
    if 'page' not in st.session_state:
        st.session_state.page = 1
        
    col1, col2, col3 = st.sidebar.columns(3)
    if col1.button("◀ Prev") and st.session_state.page > 1:
        st.session_state.page -= 1
        st.rerun()
    col2.write(f"Page {st.session_state.page}")
    if col3.button("Next ▶"):
        st.session_state.page += 1
        st.rerun()
        
    articles = fetch_articles(page=st.session_state.page, per_page=20, status=status, category=category, search=search_term)
    
    if not articles:
        st.info("No articles found matching the current filters.")
        return
        
    for a in articles:
        with st.container(border=True):
            h_col1, h_col2 = st.columns([4, 1])
            with h_col1:
                title_markdown = f"**{a.get('headline', 'No Headline')}**"
                if a.get('is_breaking'):
                    title_markdown = "🚨 :red[**BREAKING**] " + title_markdown
                st.markdown(title_markdown)
                
                c_tag = f":blue[{a.get('category', 'Uncategorized').upper()}]"
                s_tag = f":green[{a.get('source', 'Unknown')}]"
                t_tag = f"🕒 {relative_time(a.get('created_at'))}"
                st.markdown(f"{c_tag} | {s_tag} | {t_tag}")
                
            with h_col2:
                v_score = a.get('viral_score') or 0
                st.write("Viral Score")
                st.progress(min(v_score, 100) / 100.0, text=f"{v_score}/100")
            
            with st.expander("View Summaries & Details"):
                details = fetch_article_details(a['id'])
                if details and details.get('summary'):
                    s = details['summary']
                    st.markdown("### Social Media Content")
                    
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        st.markdown("**🐦 Twitter**")
                        st.code(s.get('twitter_text', 'N/A'), language='text')
                        st.markdown("**💼 LinkedIn**")
                        st.code(s.get('linkedin_text', 'N/A'), language='text')
                    with tc2:
                        st.markdown("**📸 Instagram**")
                        st.code(s.get('instagram_caption', 'N/A'), language='text')
                        st.markdown("**📘 Facebook**")
                        st.code(s.get('facebook_text', 'N/A'), language='text')
                        
                    st.markdown("**#️⃣ Hashtags**")
                    st.code(s.get('hashtags', 'N/A'), language='text')
                    
                    try:
                        img_resp = requests.get(
                            f"http://127.0.0.1:5000/api/articles/{a['id']}/thumbnail",
                            timeout=3
                        )
                        if img_resp.status_code == 200:
                            from io import BytesIO
                            st.image(
                                BytesIO(img_resp.content),
                                caption="Generated visual card",
                                use_container_width=True
                            )
                        else:
                            st.caption("Visual card not yet generated.")
                    except Exception:
                        pass
                else:
                    st.warning("No summary available for this article.")


def page_analytics():
    st.title("📊 Analytics Dashboard")
    
    stats = fetch_stats()
    if not stats:
        st.error("Stats unavailable.")
        return
        
    # 4 Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Articles", stats.get("total_articles", 0))
    m2.metric("Summarised Today", stats.get("summarised_today", 0))
    m3.metric("Breaking Today", stats.get("breaking_today", 0))
    m4.metric("Categories Tracked", len(stats.get("articles_by_category", {})))
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Articles by Category")
        cats = stats.get("articles_by_category", {})
        if cats:
            df_cats = pd.DataFrame(list(cats.items()), columns=["Category", "Count"]).set_index("Category")
            st.bar_chart(df_cats)
        else:
            st.write("No category data.")
            
    with col2:
        st.subheader("Top 5 Sources")
        tops = stats.get("top_sources", {})
        if isinstance(tops, dict) and tops:
            df_top = pd.DataFrame(list(tops.items()), columns=["Source", "Count"]).set_index("Source")
            st.bar_chart(df_top)
        else:
            st.write("No top sources data available or incorrect format.")
            
    st.subheader("Articles by Status")
    status_dict = stats.get("articles_by_status", {})
    if status_dict:
        df_status = pd.DataFrame(list(status_dict.items()), columns=["Status", "Count"])
        st.table(df_status)

    st.subheader("Latest AI Insight Report")
    try:
        resp = requests.get(f"{API_BASE}/stats", timeout=5)
        insight_resp = requests.get(f"{API_BASE}/insights", timeout=5)
        if insight_resp.status_code == 200:
            report = insight_resp.json().get("report", "")
            if report:
                st.info(report)
            else:
                st.caption("No insight report yet — run pipeline to generate one.")
    except Exception:
        pass


def page_health():
    st.title("🏥 System Health")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        auto_refresh = st.toggle("Auto-Refresh (30s)", value=False)
        
    placeholder = st.empty()
    
    if auto_refresh:
        while True:
            render_health(placeholder)
            time.sleep(30)
    else:
        render_health(placeholder)


def render_health(placeholder):
    with placeholder.container():
        health = fetch_health()
        
        pg_status = health.get("postgresql", "error")
        ol_status = health.get("ollama", "error")
        
        pg_color = "🟢 OK" if pg_status == "ok" else "🔴 ERROR"
        ol_color = "🟢 OK" if ol_status == "ok" else "🔴 ERROR"
        
        st.subheader("Services Connectivity")
        st.markdown(f"**PostgreSQL Database**: {pg_color}")
        st.markdown(f"**Ollama Local API**: {ol_color}")
        
        st.markdown("---")
        st.write("**Last Health Check Output:**")
        st.json(health)
        
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def page_control():
    st.title("⚙️ Control Panel")
    
    # --- Section 1: Pipeline Control ---
    st.subheader("Pipeline Control")
    try:
        status_resp = requests.get(f"{API_BASE}/pipeline/status", timeout=5)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            
            is_running = status_data.get("is_running", False)
            if is_running:
                st.warning("🟠 RUNNING")
            else:
                st.success("🟢 IDLE")
                
            last_run = status_data.get("last_run") or {}
            
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Discovered", last_run.get("discovered", 0))
            m2.metric("Scored", last_run.get("scored", 0))
            m3.metric("Merged", last_run.get("merged", 0))
            m4.metric("Breaking", last_run.get("breaking", 0))
            m5.metric("Summarised", last_run.get("summarised", 0))
            
            try:
                stats_r = requests.get(f"{API_BASE}/images/stats", timeout=3)
                if stats_r.status_code == 200:
                    cov = stats_r.json().get('coverage_pct', 0)
                    m6.metric("Image Coverage", f"{cov}%")
                else:
                    m6.metric("Image Coverage", "N/A")
            except:
                m6.metric("Image Coverage", "N/A")
            
            if st.button("Run Pipeline Now"):
                run_resp = requests.post(f"{API_BASE}/pipeline/run", timeout=5)
                if run_resp.status_code == 200:
                    st.toast("Pipeline started!")
                    time.sleep(1)
                    st.rerun()
                elif run_resp.status_code == 409:
                    st.error("Pipeline already running")
                else:
                    st.error("Failed to start pipeline")
                    
            if last_run.get("started_at"):
                st.write(f"**Last Run Started:** {relative_time(last_run.get('started_at'))}")
            if last_run.get("duration_sec"):
                st.write(f"**Last Run Duration:** {last_run.get('duration_sec'):.2f} seconds")
    except Exception as e:
        st.error(f"Failed to connect to Pipeline Status API: {e}")

    st.markdown("---")

    # --- Section 2: Post Approval Queue ---
    st.subheader("Approval Queue")
    try:
        pending_resp = requests.get(f"{API_BASE}/posts/pending", timeout=5)
        if pending_resp.status_code == 200:
            pending_posts = pending_resp.json()
            
            if not pending_posts:
                st.info("No posts pending approval")
            else:
                for post in pending_posts:
                    with st.container(border=True):
                        st.markdown(f"**{post.get('headline', 'No Headline')}**")
                        v_score = post.get('viral_score', 0)
                        st.progress(min(v_score, 100) / 100.0, text=f"Viral Score: {v_score}/100")
                        
                        tabs = st.tabs(["Twitter", "LinkedIn", "Instagram", "Facebook"])
                        # Using [0], [1] etc because st.tabs returns a list of containers
                        with tabs[0]:
                            st.code(post.get('twitter_text', ''), language='text')
                        with tabs[1]:
                            st.code(post.get('linkedin_text', ''), language='text')
                        with tabs[2]:
                            st.code(post.get('instagram_caption', ''), language='text')
                        with tabs[3]:
                            st.code(post.get('facebook_text', ''), language='text')
                            
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Approve", key=f"approve_{post['id']}", type="primary"):
                                if requests.post(f"{API_BASE}/posts/{post['id']}/approve").status_code == 200:
                                    st.rerun()
                        with c2:
                            if st.button("Reject", key=f"reject_{post['id']}"):
                                if requests.post(f"{API_BASE}/posts/{post['id']}/reject").status_code == 200:
                                    st.rerun()
    except Exception as e:
        st.error(f"Failed to fetch approval queue: {e}")

    st.markdown("---")

    # --- Section 3: Recent Pipeline Runs ---
    st.subheader("Pipeline History")
    try:
        history_resp = requests.get(f"{API_BASE}/pipeline/history", timeout=5)
        if history_resp.status_code == 200:
            history = history_resp.json()
            if history:
                st.dataframe(pd.DataFrame(history), use_container_width=True)
            else:
                st.write("No pipeline history found.")
    except Exception as e:
        st.error(f"Failed to load pipeline history: {e}")


# --- Main App Routing ---
pages = {
    "Articles Feed": page_feed,
    "Analytics": page_analytics,
    "System Health": page_health,
    "Control Panel": page_control
}

st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(pages.keys()))

pages[selection]()
