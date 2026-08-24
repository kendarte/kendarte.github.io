from evennia import Command

from commands.world_input_v74_commands import _clone
from commands.world_input_v82_commands import TEST_TEXT, TEST_TOPIC
from services.grounded_dialogue_renderer import validate_grounded_dialogue_text
from services.styled_grounded_dialogue_renderer import (
    STYLED_GROUNDED_DIALOGUE_BUILD,
    build_safe_styled_fallback,
    build_styled_grounded_dialogue_request,
    render_styled_grounded_dialogue_sync,
    validate_style_delivery,
)


V0821_VALIDATION_BUILD = "0.82.1-targeted-enforced-voice-delivery"

STYLE_A = {
    "register": "FORMAL",
    "warmth": "RESERVED",
    "directness": "DIRECT",
    "verbosity": "TERSE",
    "cadence": "CLIPPED",
    "familiarity_band": "FAMILIAR",
}

STYLE_B = {
    "register": "CASUAL",
    "warmth": "WARM",
    "directness": "BALANCED",
    "verbosity": "NORMAL",
    "cadence": "MEASURED",
    "familiarity_band": "ESTABLISHED",
}


class CmdSizaValidateV821(Command):
    key = "siza-validate-v821"
    aliases = ["validate-v821"]
    locks = "cmd:perm(Admin)"

    def func(self):
        actor = self.caller
        original_state = _clone(
            {
                "knowledge": getattr(actor.db, "knowledge", {}),
                "knowledge_facts": getattr(actor.db, "knowledge_facts", []),
                "memories": getattr(actor.db, "memories", []),
                "relationships": getattr(actor.db, "relationships", {}),
                "discovered_facts": getattr(actor.db, "discovered_facts", []),
            }
        )
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.82.1 | {V0821_VALIDATION_BUILD} ===")
        self.caller.msg(
            "targeted voice rerun: closed style enums -> mandatory surface realization -> grounded validation -> deterministic styled fallback"
        )

        try:
            request_a = build_styled_grounded_dialogue_request(
                "Mara Vensal", TEST_TOPIC, TEST_TEXT, style_context=STYLE_A
            )
            request_b = build_styled_grounded_dialogue_request(
                "Mara Vensal", TEST_TOPIC, TEST_TEXT, style_context=STYLE_B
            )
            directives_a = list(request_a.get("style_directives") or [])
            directives_b = list(request_b.get("style_directives") or [])
            check(
                "closed-enums-now-produce-explicit-high-signal-delivery-directives",
                any("Máximo 14 palabras" in row for row in directives_a)
                and any("Empieza exactamente con 'Mira,'" in row for row in directives_b)
                and TEST_TEXT in str((request_a.get("provider_payload") or {}).get("prompt") or "")
                and TEST_TEXT in str((request_b.get("provider_payload") or {}).get("prompt") or ""),
                f"A_directives={len(directives_a)} B_directives={len(directives_b)}",
            )

            neutral_output = "El sello fue estampado tras el cierre de la dársena."

            def neutral_provider(payload, **kwargs):
                return {"status": "OK", "text": neutral_output}

            warm_mismatch = render_styled_grounded_dialogue_sync(
                "Mara Vensal",
                TEST_TOPIC,
                TEST_TEXT,
                style_context=STYLE_B,
                fallback_text=TEST_TEXT,
                provider_callable=neutral_provider,
            )
            expected_warm_fallback = build_safe_styled_fallback(TEST_TEXT, STYLE_B)
            check(
                "neutral-qwen-output-can-no-longer-pass-as-casual-warm-established-voice",
                warm_mismatch.get("status") == "FALLBACK_STYLE_MISMATCH"
                and str(warm_mismatch.get("display_text") or "") == expected_warm_fallback
                and str(expected_warm_fallback).startswith("Mira, por lo que sé,"),
                f"status={warm_mismatch.get('status')} text={warm_mismatch.get('display_text')!r}",
            )

            compliant_warm_text = (
                "Mira, por lo que sé, el sello del turno de ceniza fue estampado después del cierre de la dársena."
            )

            def compliant_warm_provider(payload, **kwargs):
                return {"status": "OK", "text": compliant_warm_text}

            warm_ok = render_styled_grounded_dialogue_sync(
                "Mara Vensal",
                TEST_TOPIC,
                TEST_TEXT,
                style_context=STYLE_B,
                fallback_text=TEST_TEXT,
                provider_callable=compliant_warm_provider,
            )
            check(
                "grounded-provider-output-with-required-warm-casual-surface-is-accepted",
                warm_ok.get("status") == "STYLED_GROUNDED_DIALOGUE_RENDERED"
                and warm_ok.get("display_text") == compliant_warm_text
                and (warm_ok.get("style_validation") or {}).get("status") == "STYLE_DELIVERY_ACCEPTED",
                f"status={warm_ok.get('status')}",
            )

            formal_reject_text = "Mira, el sello fue estampado tras el cierre de la dársena."
            formal_style_check = validate_style_delivery(
                formal_reject_text,
                style_context=STYLE_A,
            )
            check(
                "formal-reserved-profile-rejects-the-warm-casual-surface-cue",
                formal_style_check.get("valid") is False
                and formal_style_check.get("status") == "STYLE_TOO_CASUAL",
                f"status={formal_style_check.get('status')}",
            )

            before_live = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "knowledge_facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "discovered_facts": getattr(actor.db, "discovered_facts", []),
                }
            )

            self.caller.msg(f"LIVE V0821 STYLE A: {STYLE_A}")
            live_a = render_styled_grounded_dialogue_sync(
                "Mara Vensal",
                TEST_TOPIC,
                TEST_TEXT,
                style_context=STYLE_A,
                fallback_text=TEST_TEXT,
                timeout=60,
            )
            self.caller.msg(f"LIVE V0821 STYLE A RESULT: {live_a.get('display_text')}")

            self.caller.msg(f"LIVE V0821 STYLE B: {STYLE_B}")
            live_b = render_styled_grounded_dialogue_sync(
                "Mara Vensal",
                TEST_TOPIC,
                TEST_TEXT,
                style_context=STYLE_B,
                fallback_text=TEST_TEXT,
                timeout=60,
            )
            self.caller.msg(f"LIVE V0821 STYLE B RESULT: {live_b.get('display_text')}")

            text_a = str(live_a.get("display_text") or "").strip()
            text_b = str(live_b.get("display_text") or "").strip()
            ground_a = validate_grounded_dialogue_text(
                text_a, npc_name="Mara Vensal", topic=TEST_TOPIC, fact_text=TEST_TEXT
            )
            ground_b = validate_grounded_dialogue_text(
                text_b, npc_name="Mara Vensal", topic=TEST_TOPIC, fact_text=TEST_TEXT
            )
            style_a_check = validate_style_delivery(text_a, STYLE_A)
            style_b_check = validate_style_delivery(text_b, STYLE_B)

            check(
                "live-profiles-now-have-measurably-distinct-grounded-voice-surfaces",
                bool(ground_a.get("valid"))
                and bool(ground_b.get("valid"))
                and bool(style_a_check.get("valid"))
                and bool(style_b_check.get("valid"))
                and text_a != text_b
                and not text_a.lower().startswith(("mira,", "bueno,"))
                and text_b.lower().startswith(("mira,", "bueno,")),
                f"A_status={live_a.get('status')} B_status={live_b.get('status')} distinct={text_a != text_b}",
            )

            after_live = _clone(
                {
                    "knowledge": getattr(actor.db, "knowledge", {}),
                    "knowledge_facts": getattr(actor.db, "knowledge_facts", []),
                    "memories": getattr(actor.db, "memories", []),
                    "relationships": getattr(actor.db, "relationships", {}),
                    "discovered_facts": getattr(actor.db, "discovered_facts", []),
                }
            )
            check(
                "v0821-style-rendering-remains-exactly-read-only",
                before_live == after_live == original_state,
                f"build={STYLED_GROUNDED_DIALOGUE_BUILD}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg("")
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: v0.82 routing/style context unchanged; v0.82.1 only strengthens presentation realization and fallback while the v0.81 grounding guard remains factual authority"
        )
        self.caller.msg("========================================================")
