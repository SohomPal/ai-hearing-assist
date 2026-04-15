def adjust_wdrc(intent, params):
    """
    params = {
        "bands": [
            {"tk_dB": ..., "cr": ..., "gain_dB": ..., "atk_ms": ..., "rel_ms": ...},
            ...
        ]
    }

    returns updated params
    """

    p = {"bands": [b.copy() for b in params["bands"]]}
    bands = p["bands"]

    def clamp(v, lo, hi):
        return max(lo, min(v, hi))

    # ------------------------
    # LOUDNESS
    # ------------------------
    if intent == "LOUDNESS_INCREASE":
        for b in bands:
            b["gain_dB"] += 1.5

    elif intent == "LOUDNESS_DECREASE":
        for b in bands:
            b["gain_dB"] -= 1.5

    # ------------------------
    # SOFT SOUND BOOST
    # ------------------------
    elif intent == "SOFT_BOOST_INCREASE":
        for b in bands:
            b["tk_dB"] -= 2.5      # activate compression earlier
            b["gain_dB"] += 0.5

    elif intent == "SOFT_BOOST_DECREASE":
        for b in bands:
            b["tk_dB"] += 2.5
            b["gain_dB"] -= 0.5

    # ------------------------
    # CLARITY
    # ------------------------
    elif intent == "CLARITY_INCREASE":

        for i in [3,4]:  # bands 4–5 (speech region)
            bands[i]["gain_dB"] += 1.5
            bands[i]["cr"] += 0.15

    elif intent == "CLARITY_DECREASE":

        for i in [3,4]:
            bands[i]["gain_dB"] -= 1.5
            bands[i]["cr"] -= 0.15

    # ------------------------
    # BRIGHTNESS
    # ------------------------
    elif intent == "BRIGHTNESS_INCREASE":

        for i in [4,5]:   # high bands
            bands[i]["gain_dB"] += 1.5

    elif intent == "BRIGHTNESS_DECREASE":

        for i in [4,5]:
            bands[i]["gain_dB"] -= 1.5

    # ------------------------
    # SAFETY LIMITS
    # ------------------------
    for b in bands:

        b["gain_dB"] = clamp(b["gain_dB"], -6, 12)
        b["cr"] = clamp(b["cr"], 1.0, 4.0)
        # b["tk_dB"] = clamp(b["tk_dB"], -60, -10)
        b["atk_ms"] = clamp(b["atk_ms"], 5, 50)
        b["rel_ms"] = clamp(b["rel_ms"], 50, 500)

    return p