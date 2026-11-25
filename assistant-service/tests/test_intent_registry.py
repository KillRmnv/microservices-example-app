from app.models import intent as intents


def test_category_intents_map_to_event_categories():
    spec = intents.spec("find_event_theatre")
    assert spec.scope == "events"
    assert spec.categories == ("theatre",)


def test_venue_intents_map_to_rubrics():
    spec = intents.spec("find_venue_cafe")
    assert spec.scope == "venues"
    assert spec.rubrics == ("Кафе",)


def test_unknown_intent_falls_back_to_generic_events():
    assert intents.spec("drop_tables").scope == "events"


def test_capabilities_and_unsupported_are_not_dialogue_intents():
    assert "capabilities" not in intents.DIALOGUE_INTENTS
    assert "unsupported" not in intents.DIALOGUE_INTENTS
    assert "find_venue_bar" in intents.DIALOGUE_INTENTS
    assert "find_event_sport" in intents.DIALOGUE_INTENTS


def test_vocabulary_derives_from_the_intent_registry():
    from app.models import vocabulary

    assert set(vocabulary.EVENT_CATEGORY_SET) == {
        categories[0] for categories in intents.EVENT_INTENTS.values()}
    assert len(vocabulary.EVENT_CATEGORIES) == 7
    expected = [rubric for rubrics in intents.VENUE_INTENTS.values()
                for rubric in rubrics]
    assert list(vocabulary.VENUE_RUBRICS) == list(dict.fromkeys(expected))
