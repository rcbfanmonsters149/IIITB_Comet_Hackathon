from core.fusion_engine import FusionEngine

def test_all():
    print("=" * 60)
    print(" IIIT-B SMART CAMPUS ACCESS CONTROL - FUSION TEST MATRIX")
    print("=" * 60)
    engine = FusionEngine()
    scenarios = ["NORMAL", "PHOTO_ATTACK", "WALK_BY", "STOLEN_PHONE"]

    for sc in scenarios:
        engine.set_scenario_override(sc)
        res = engine.evaluate_access()
        mcu_state = engine.mcu.get_status()
        print(f"Scenario: {sc:<15} | Decision: {res['decision']:<28} | Score: {res['composite_score']*100:.1f}% | Relay: {mcu_state['relay_state']:<8} | LED: {mcu_state['rgb_led']}")

    print("=" * 60)
    print("All multi-modal fusion tests executed successfully!")

if __name__ == "__main__":
    test_all()
