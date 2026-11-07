import runpy,pathlib
runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1]/'gemini-native500-gcs/ab160_offline.py'),run_name='__main__')
