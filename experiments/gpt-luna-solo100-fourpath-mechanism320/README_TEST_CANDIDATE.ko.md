# TEST 후보 재현 계약 — 최종 선택 전 준비본

이 폴더는 동결된 프롬프트와 최종 선택 증거를 확인해 API **요청 본문만** 만드는 오프라인 도구다. 실제 후보 선택, 생성 API 실행, 실사용 합격 또는 SERVICE 적용 승인을 뜻하지 않는다. 현재 선택 template의 네 경로와 SHA는 모두 비어 있으며 로더는 이 template을 거부한다.

`candidate_contract.py`에는 API 클라이언트, 네트워크 송신, API 키, 환경변수 조회, 자동 재시도, 모델 fallback, 연속 FIRST/BACK 실행 또는 캠페인 잠금 해제 기능이 없다. 일반 배포본에는 이 코드·합성 테스트·빈 template만 넣는다. 실제 프롬프트, 선택 증거, 종료 controller, 대화 입력과 생성한 요청 본문은 소유자 전용 증거 ZIP에서 취급한다.

## 최종 평가 후 작성할 항목

이 절은 담당자가 FINAL 결과와 종료 증거를 확인한 뒤 채울 절차다. 준비 중인 template을 연구 결론이나 종료 증거로 사용하지 않는다.

1. 실제 동결 `PROMPTS.json`의 바이트를 그대로 보존한다. 구조는 `BASE: {KF, KB, LF, LB}`, `HLEX: {KF, LF}`, `HPROP: {KF, LF}`, `HBACK: {KB, LB}`의 총 10개 문자열이다.
2. 최종 평가에서 선택한 네 경로의 prompt ID를 `FINAL_SELECTION.json`에 기입한다. FIRST 경로는 BASE/HLEX/HPROP, BACK 경로는 BASE/HBACK 가운데 해당 경로에 실제 존재하는 ID만 허용한다. 선택하지 못했다면 빈 template을 그대로 두고 재현 후보를 확정했다고 보고하지 않는다.
3. `prompt_file_sha256`은 PROMPTS 파일의 정확한 바이트 SHA-256이다. `prompt_sha256`은 각 경로에서 선택한 문자열을 수정 없이 UTF-8로 인코딩한 SHA-256이다. 줄바꿈과 공백도 그대로 보존한다.
4. 실제 종료 controller를 별도 파일로 보존하고 그 바이트 SHA-256을 `controller_file_sha256`에 기입한다. loader는 해당 캠페인의 `status=CLOSED_LOCKED`, `enabled=false`, 정수 `max_new=0`을 모두 요구한다. 이 준비본은 controller를 만들거나 기존 controller를 변경하지 않는다.
5. 위 증거를 확인한 뒤에만 선택 manifest의 `artifact_status`를 `FINALIZED_TEST_CONTRACT`로 바꾼다. 해당 값은 검토된 TEST 계약이라는 뜻이며 번역 품질 PASS나 운영 승인을 대신하지 않는다.
6. 완성된 `FINAL_SELECTION.json`의 바이트 SHA-256을 별도 검증된 인수인계/manifest에 기록한다. 호출자는 그 외부 값을 `expected_selection_sha256`으로 전달한다. 같은 파일을 읽어 방금 계산한 값을 그대로 신뢰하는 것만으로는 출처 검증이 되지 않는다.

## 함수 계약

| 함수/방향 | 선택 경로 | 입력 |
| --- | --- | --- |
| `build_first(text, "K2L")` | KF | 한국어 최초 원문 |
| `build_first(text, "L2K")` | LF | 라오어 최초 원문 |
| `build_back(actual_first, "K2L")` | KB | 위 KF에서 실제 완료된 라오어 FIRST 문자열만 |
| `build_back(actual_first, "L2K")` | LB | 위 LF에서 실제 완료된 한국어 FIRST 문자열만 |

BACK의 `direction`은 FIRST와 같은 진행 방향이다. FIRST가 한국어→라오어였다면 BACK도 `K2L`을 지정한다. BACK 함수에는 최초 원문, 정답, 원문 요약 또는 평가를 받는 인자가 없다. 객체는 이전 FIRST 입력을 저장하지 않으며 BACK 본문을 만들 때 참조하지 않는다. 입력 문자열의 공백, 줄바꿈, 문자 등을 정규화하지 않는다.

이 함수의 반환값은 plain dict이며 호출이 실행된 결과가 아니다. FIRST의 성공·종료 상태, 실제 모델/tier, 출력의 출처와 완료 여부를 문자열만으로 확인할 수 없다. 별도의 승인된 실행 환경이 생길 경우 그 환경에서 이를 검증한 실제 FIRST 출력만 BACK에 전달해야 한다. FIRST 오류를 원문이나 상식으로 고쳐서 BACK에 넣지 않는다.

고정 API 설정은 다음과 같다. 요청에 재시도용 비표준 필드를 추가하지 않는다.

| 항목 | 값 |
| --- | --- |
| `model` | `gpt-6-luna` |
| `reasoning.effort` | `none` |
| `service_tier` | `fast` |
| `stream` | `true` |
| `store` | `false` |
| `max_output_tokens` | `4096` |
| 자동 재시도 / fallback / 숨은 생성 | `0 / 0 / 0` |
| 도구 실행 허용 / 신규 호출량 | `enabled=false / max_new=0` |

정상 사용 방법은 `CandidateContract.load(prompts_path, selection_path, controller_path, expected_selection_sha256=검증된_SHA)`로 검증한 뒤 FIRST 또는 BACK 요청 하나의 dict만 만드는 것이다. 반환 본문에는 실제 개인 대화와 프롬프트가 포함될 수 있으므로 공개 로그에 출력하지 않는다. `execution_policy`와 `evidence_hashes`는 사본으로 반환된다. 오류 메시지와 객체 repr에는 대화나 프롬프트를 포함하지 않는다.

이 계약은 종료된 캠페인의 남은 예산을 재활성화하지 않는다. 실제 신규 송신에는 별도 사용자 승인과 새 캠페인/원장 및 전송 검증이 필요하다. 기존 SERVICE, main, 운영 프롬프트와 DB는 변경하지 않는다. 현재 연구의 품질·속도 결과와 선택 결론은 root가 작성할 최종 보고서에 별도로 연결한다.

## 무료 검증

이 폴더에서 `python -m unittest -v test_candidate_contract.py`를 실행한다. 테스트는 임시 폴더의 합성 프롬프트·가상 종료 증거만 사용하며 실제 대화/실험 결과나 API에 접근하지 않는다. 선택 SHA, 프롬프트/종료 SHA, 경로 오류, 활성 controller 거부, exact 입력 보존, BACK 인자 제한과 반환 객체 간 격리를 확인한다.

최종 전달 시 실제 선택 manifest 및 controller가 추가로 검증되었는지, 기술검사와 번역 품질 검토를 구분했는지 최종 보고서에 기록한다. 준비본의 합성 테스트 통과를 실제 후보의 품질 PASS로 보고하지 않는다.
