from dotenv import load_dotenv
load_dotenv()

from pipeline.master_pipeline import MasterPipeline

print('[RUN_V2] Starting single pipeline run...')

result = MasterPipeline().run()

print('[RUN_V2] Complete:')
for stage, data in result.items():
    status   = data.get('status', '?')
    duration = data.get('duration', 0)
    print(f'  {stage}: {status} ({duration}s)')
