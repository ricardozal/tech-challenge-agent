"""The reply ends with the exact question the code decided (Principle II)."""

from agent.questions import Q_OWN_NAME, end_with_question

Q_ID = "Envíame una foto de tu identificación oficial (INE o pasaporte)."


def test_trailing_variant_of_the_question_is_replaced_by_the_exact_text():
    reply = "Hola, Laura. Para continuar con tu proceso, ¿el auto está a tu nombre?"
    assert end_with_question(reply, Q_OWN_NAME.text) == "Hola, Laura. Para continuar con tu proceso, ¿El auto está a tu nombre?"
    wrapped = "Ahora necesito tus documentos. ¿Envíame una foto de tu identificación oficial (INE o pasaporte)?"
    assert end_with_question(wrapped, Q_ID) == f"Ahora necesito tus documentos. {Q_ID}"


def test_missing_question_is_appended_and_exact_endings_are_kept():
    assert end_with_question("Gracias.", Q_OWN_NAME.text) == f"Gracias. {Q_OWN_NAME.text}"
    exact = f"Gracias. {Q_OWN_NAME.text}"
    assert end_with_question(exact, Q_OWN_NAME.text) == exact
    assert end_with_question("Listo, tu caso pasa a la financiera.", None) == "Listo, tu caso pasa a la financiera."
