from dotenv import load_dotenv
load_dotenv()
from agents.summarisation_agent import SummarisationAgent
try:
    print("SummarisationAgent manual run started...")
    agent = SummarisationAgent()
    count = agent.run()
    print('Summarised:', count)
except Exception as e:
    print(f"Error: {e}")
