from pathlib import Path
import hashlib,importlib.metadata,json
import laonlp
root=Path(laonlp.__file__).parent/'corpus'
expected={'Lao-Dictionary.txt':'822671c5aa773d0a6f138b882b2810b3ac94251c27d7286d7b974e9c5c2d488d','lo_spellcheck_dict.txt':'a044530de6fa0be19009e9cbeebb43a9b7e94494cd4eb54244be7fe3c15a6eb8','lao-wannaphong.txt':'da7f267293695781a7a677642c28915b98e25678290605f48e11b5262cc5e320','wiktionary-20210720.txt':'b518d5f2323f2e37366af31c195b83d43f0d933eb71da764b5058ef4f8144bee'}
for package,version in {'LaoNLP':'1.3.0','pythainlp':'5.4.0','tzdata':'2026.6'}.items():assert importlib.metadata.version(package)==version
for filename,digest in expected.items():assert hashlib.sha256((root/filename).read_bytes()).hexdigest()==digest
print('Frozen dictionary hashes and dependency versions verified; model calls 0')
