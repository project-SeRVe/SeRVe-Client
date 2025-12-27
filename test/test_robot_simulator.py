#!/usr/bin/env python3
"""
로봇 시뮬레이터 기능 테스트
Edge 서버 없이 시뮬레이터 로직만 검증
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from robot_simulator import generate_normal_data, generate_attack_data, ATTACK_PAYLOADS

def test_normal_data_generation():
    """정상 센서 데이터 생성 테스트"""
    print("\n" + "=" * 70)
    print("  테스트 1: 정상 센서 데이터 생성")
    print("=" * 70)

    try:
        data = generate_normal_data()
        print(f"\n생성된 정상 데이터:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # 필수 필드 검증
        assert "robot_id" in data, "robot_id 필드 누락"
        assert "temperature" in data, "temperature 필드 누락"
        assert "pressure" in data, "pressure 필드 누락"
        assert "timestamp" in data, "timestamp 필드 누락"
        assert "metadata" in data, "metadata 필드 누락"

        # 값 범위 검증
        assert 20.0 <= data["temperature"] <= 30.0, f"온도 범위 오류: {data['temperature']}"
        assert 95.0 <= data["pressure"] <= 105.0, f"압력 범위 오류: {data['pressure']}"
        assert data["metadata"]["location"] == "Factory Floor A", "위치 정보 오류"
        assert data["metadata"]["status"] == "operational", "상태 정보 오류"

        print("\n✓ 검증: 정상 센서 데이터가 올바르게 생성됩니다")
        return True

    except AssertionError as e:
        print(f"\n✗ 검증 실패: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_attack_data_generation():
    """SQL Injection 공격 데이터 생성 테스트"""
    print("\n" + "=" * 70)
    print("  테스트 2: SQL Injection 공격 데이터 생성")
    print("=" * 70)

    try:
        # 여러 번 생성하여 다양한 주입 패턴 확인
        attack_data_samples = []
        injection_found = False

        for i in range(10):
            data = generate_attack_data()
            attack_data_samples.append(data)

            # 어느 필드에 공격 페이로드가 주입되었는지 확인
            data_str = json.dumps(data)
            for payload in ATTACK_PAYLOADS:
                if payload in data_str:
                    injection_found = True
                    print(f"\n[Sample {i+1}] 공격 페이로드 감지:")
                    print(f"  페이로드: {payload}")
                    print(f"  전체 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
                    break

        assert injection_found, "공격 페이로드가 데이터에 주입되지 않음"

        print(f"\n✓ 검증: SQL Injection 공격 페이로드가 올바르게 생성됩니다")
        print(f"  - 총 {len(ATTACK_PAYLOADS)}개의 공격 패턴 정의됨")
        print(f"  - 공격 패턴 예시: {ATTACK_PAYLOADS[:3]}")

        return True

    except AssertionError as e:
        print(f"\n✗ 검증 실패: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_attack_payloads_coverage():
    """공격 페이로드 다양성 테스트"""
    print("\n" + "=" * 70)
    print("  테스트 3: 공격 페이로드 다양성 검증")
    print("=" * 70)

    try:
        print(f"\n정의된 공격 페이로드 ({len(ATTACK_PAYLOADS)}개):")
        for i, payload in enumerate(ATTACK_PAYLOADS, 1):
            print(f"  {i}. {payload}")

        # 공격 유형 분류
        drop_attacks = [p for p in ATTACK_PAYLOADS if "DROP" in p.upper()]
        delete_attacks = [p for p in ATTACK_PAYLOADS if "DELETE" in p.upper()]
        union_attacks = [p for p in ATTACK_PAYLOADS if "UNION" in p.upper()]
        or_attacks = [p for p in ATTACK_PAYLOADS if "OR" in p.upper()]

        print(f"\n공격 유형 분류:")
        print(f"  - DROP TABLE 공격: {len(drop_attacks)}개")
        print(f"  - DELETE 공격: {len(delete_attacks)}개")
        print(f"  - UNION SELECT 공격: {len(union_attacks)}개")
        print(f"  - OR 조건 우회 공격: {len(or_attacks)}개")

        assert len(ATTACK_PAYLOADS) >= 5, f"공격 패턴이 너무 적음 ({len(ATTACK_PAYLOADS)}개)"

        print(f"\n✓ 검증: 다양한 SQL Injection 공격 패턴이 정의되어 있습니다")
        return True

    except AssertionError as e:
        print(f"\n✗ 검증 실패: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    print("=" * 70)
    print("  로봇 시뮬레이터 기능 테스트")
    print("=" * 70)
    print("\n검증 항목:")
    print("  1. 정상 센서 데이터 생성")
    print("  2. SQL Injection 공격 데이터 생성")
    print("  3. 공격 페이로드 다양성")

    results = {}

    # 테스트 실행
    results["정상 데이터 생성"] = test_normal_data_generation()
    results["공격 데이터 생성"] = test_attack_data_generation()
    results["공격 패턴 다양성"] = test_attack_payloads_coverage()

    # 결과 요약
    print("\n" + "=" * 70)
    print("  테스트 결과 요약")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ 통과" if result else "❌ 실패"
        print(f"  {status} - {test_name}")

    print()
    print(f"총 {total}개 테스트 중 {passed}개 통과")

    if passed == total:
        print("\n🎉 모든 로봇 시뮬레이터 테스트 통과!")
    else:
        print(f"\n⚠️  {total - passed}개 테스트 실패")

    print("=" * 70)

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
