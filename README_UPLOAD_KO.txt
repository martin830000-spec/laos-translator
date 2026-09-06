V3.60.2 V2.87 ↔ 현재 원클릭 비교진단 FIXED

업로드 방법
1) 이 ZIP의 파일을 모두 압축 해제합니다.
2) GitHub Pages에서 현재 index.html이 있는 같은 폴더에 모든 파일을 그대로 업로드합니다.
3) index.html과 version.json은 같은 이름 파일을 교체합니다.
4) 기존 diagnostic.html은 삭제하지 않아도 됩니다. 이번 index.html은 더 이상 diagnostic.html을 사용하지 않습니다.
5) GitHub Pages 반영 후 앱을 닫았다 다시 열고 평소 관리자 진단 버튼을 누릅니다.

정상 화면 제목:
V2.87 ↔ V3.60.2 통합 비교진단

이번 수정 이유:
이전 패키지는 diagnostic.html?v=V3.60.2라는 기존과 동일한 주소를 사용해 GitHub Pages/CDN/브라우저 캐시에서 과거 V3.60.2 진단기가 반환될 수 있었습니다.
이번 패키지는 완전히 다른 파일명 diagnostic-compare-v287-v3602-v1.html을 사용하며, 열 때마다 해시+현재시각 cache-buster를 붙입니다.
