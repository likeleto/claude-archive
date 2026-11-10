#!/usr/bin/env python3
"""Generate an entirely fictional Claude export; no personal source data is used."""
import argparse
import json
import uuid
import zipfile
from pathlib import Path


def ident(label):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "claude-archive-demo/" + label))


def make_demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "demo-export.zip"
    if path.exists():
        raise ValueError("Demo already exists: " + str(path))
    stamp = "2026-01-01T12:00:00Z"
    # Keep stable demo IDs so existing links still open after content updates.
    project = {"uuid": ident("garden"), "name": "Claude Archive · Начните здесь", "description": "Знакомство с проектом через вымышленные диалоги.",
               "prompt_template": "Объясни создание локального архива и необязательный перенос. Это вымышленные данные для демо, а не экспорт реального пользователя.", "created_at": stamp}
    other = {"uuid": ident("recipes"), "name": "Пробный проект", "description": "Демопроект для проверки назначения диалогов."}
    def chat(label, title, question, answer, pid=None):
        c = {"uuid": ident(label), "name": title, "created_at": stamp, "updated_at": stamp,
             "chat_messages": [{"uuid": ident(label + "-user"), "sender": "human", "text": question, "created_at": stamp, "content": [{"type": "text", "text": question}]},
                               {"uuid": ident(label + "-assistant"), "sender": "assistant", "text": answer, "created_at": stamp, "content": [{"type": "text", "text": answer}]}]}
        if pid:
            c["project_uuid"] = pid
        return c
    chats = [chat("layout", "01 · Что такое Claude Archive?",
                  "Хочу сохранить переписки и артефакты из Claude. Обязательно ли переходить в Codex, чтобы пользоваться этим проектом?",
                  "**Нет. Сначала сохраните локальный архив, а решение о переносе примите позже.**\n\n"
                  "Claude Archive превращает экспорт Claude в библиотеку с поиском по диалогам, проектами, документами и доступными HTML-артефактами. Исходные ZIP остаются без изменений.\n\n"
                  "**Посмотрите пример:** справа открыт HTML-артефакт «Как работает Claude Archive». Во втором диалоге вы найдёте инструкцию получения экспорта и чек-лист, в третьем — примеры ограничений данных.\n\n"
                  "**Для своего архива:** скачайте проект, откройте его папку в локальном ИИ-агенте и напишите: «Прочитай AGENTS.md и используй claude-archive, чтобы собрать и проверить мой экспорт». Нужен Python 3.9+; для архива не нужны Codex и API-ключи.\n\n"
                  "Все записи здесь вымышлены. Демо на сайте позволяет читать их и менять назначения проектов только в вашем браузере. Сборка личного архива и перенос выполняются на вашем компьютере."),
             chat("watering", "02 · Как получить и сохранить экспорт?",
                  "С чего начать? Как получить файлы экспорта Claude и передать их агенту?",
                  "**1. Запросите экспорт.** В Claude на компьютере откройте Settings → Privacy → Export data. Дождитесь письма и откройте ссылку на скачивание. [Официальная инструкция](https://support.claude.com/en/articles/9450526-export-your-claude-data).\n\n"
                  "**2. Скачайте файлы из manifest.** Если вместо ZIP вы получили manifest-….json, это список файлов, а не сами переписки. В нашем примере в нём четыре архива: conversations-000.zip, projects-000.zip, frames-000.zip и light_metadata-000.zip. В вашей выгрузке количество может отличаться: скачайте все файлы из списка.\n\n"
                  "**Можно поручить агенту:** «Прочитай этот manifest JSON и скачай все файлы из data_files по export_url, сохранив имена filename, в отдельную личную папку. Проверь, что все архивы скачаны полностью». Агенту нужен доступ к файлу и сети. Если скачивание требует входа в Claude через браузер, откройте ссылки самостоятельно. Ссылки временные и могут перестать работать после использования — скачивайте файлы сразу.\n\n"
                  "**3. Соберите архив.** Откройте скачанный проект в локальном агенте и попросите прочитать AGENTS.md и использовать claude-archive для папки с ZIP. Агент проверит состав, уточнит связи проектов и соберёт локальный просмотрщик. Можно сохранить все диалоги, включая неназначенные. Исходные ZIP сохраните отдельно.\n\n"
                  "**Дальше — по желанию.** Выбранные диалоги можно перенести в Codex после проверки плана и изолированной пробы. Импортёр экспериментальный. Рабочие папки с контекстом проектов и артефактами нужно открыть в Codex самостоятельно. Подробности — в чек-листе справа.", project["uuid"]),
             chat("unassigned", "03 · Чего может не быть в экспорте?",
                  "Что происходит, если в экспорте не хватает связей проектов, версий или файлов?",
                  "**Связи проектов.** В некоторых выгрузках их нет. Этот диалог изначально оставлен без назначения. Попробуйте выбрать в поле «Проект» вариант «Пробный проект» — диалог появится в этой группе слева.\n\n"
                  "В локальной версии изменение записывается в organization.json. В демо на сайте оно сохраняется только в вашем браузере и не влияет на других посетителей.\n\n"
                  "**Есть скриншоты или текст панели Claude?** Передайте их агенту для восстановления связей. У первого демодиалога связь отсутствует в исходном экспорте и восстановлена по вымышленной копии панели. Разверните «Основание назначения» под выбором проекта в первом диалоге; пример панели есть в чек-листе второго. Спорные совпадения требуют уточнения.\n\n"
                  "**Недоступные версии:** у артефакта в первом диалоге указана старая версия, которая специально отсутствует в данных. Выберите её, чтобы увидеть соответствующее сообщение. Отсутствующий текст старых версий не выдумывается.\n\n"
                  "**Вложения:** во втором диалоге есть вымышленное текстовое вложение. Разверните его, чтобы прочитать извлечённый текст. Исходные файлы вложений могут отсутствовать в реальном экспорте.\n\n"
                  "**HTML-артефакты.** Предпросмотр не загружает внешние библиотеки и данные из сети, поэтому некоторые артефакты могут работать не полностью.\n\n"
                  "**Попробуйте поиск:** введите слово «выдумывается» из объяснения выше — в списке останется этот диалог.")]
    chats[1]["chat_messages"][0]["attachments"] = [{"file_name": "заметки-об-экспорте.txt", "extracted_content": "Вымышленное вложение: запросить экспорт → получить manifest → скачать все перечисленные ZIP → проверить состав → собрать локальный архив. JSON со ссылками не заменяет сами архивы."}]
    # Link artifacts explicitly; their internal IDs need not appear in visible prose.
    chats[0]["chat_messages"][1]["artifact_id"] = ident("diagram")
    chats[1]["chat_messages"][1]["artifact_id"] = ident("page")
    artifact = {"id": ident("diagram"), "kind": "html", "active_version": ident("diagram-v2"),
                "versions": [{"id": ident("diagram-v1"), "title": "Как работает Claude Archive", "created_at": "2025-12-31T12:00:00Z"},
                             {"id": ident("diagram-v2"), "title": "Как работает Claude Archive", "created_at": stamp}]}
    page = {"id": ident("page"), "kind": "page", "active_version": ident("page-v1"),
            "versions": [{"id": ident("page-v1"), "title": "Чек-лист архива и переноса", "created_at": stamp}]}
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as z:
        def put(name, value):
            z.writestr(name, json.dumps(value, ensure_ascii=False))
        put("conversations.json", chats)
        for p in (project, other):
            put("projects/" + p["uuid"] + ".json", p)
        for a in (artifact, page):
            put("artifacts/" + a["id"] + "/artifact.json", a)
        z.writestr("artifacts/" + artifact["id"] + "/versions/" + artifact["active_version"] + ".html",
                   '<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Как работает Claude Archive</title>'
                   '<style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#f4f1e9;color:#29271f;font:15px/1.55 system-ui}'
                   '.tag{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8b4e35}h1{font:38px/1.08 Georgia,serif;margin:14px 0}h2{font-size:16px;margin:0 0 5px}'
                   '.intro{color:#666155}.steps{display:grid;gap:10px;margin:24px 0}.step{background:#fffdf9;border:1px solid #ddd6c8;border-radius:12px;padding:16px}'
                   '.number{color:#9d5736;font:12px ui-monospace,monospace;margin-bottom:5px}.step p{margin:0;color:#666155;font-size:13px}.optional{background:#e7eee2;border-color:#c7d2bf}'
                   '.note{font-size:12px;color:#666155;border-top:1px solid #d7d0c2;padding-top:16px}</style></head><body>'
                   '<div class="tag">Claude Archive · интерактивное демо</div><h1>Сохраните историю.<br>Выберите, что дальше.</h1>'
                   '<p class="intro">Запросите экспорт Claude, скачайте все ZIP из manifest и соберите локальную библиотеку.</p><div class="steps">'
                   '<section class="step"><div class="number">01 / ПРОВЕРКА И СВЯЗИ</div><h2>Разберитесь в экспорте</h2><p>Проверьте доступные данные, связи проектов и недостающие версии.</p></section>'
                   '<section class="step"><div class="number">02 / СБОРКА И ПРОСМОТР</div><h2>Ваш архив на вашем компьютере</h2><p>Ищите диалоги, читайте документы и открывайте артефакты. Сохраните исходные ZIP.</p></section>'
                   '<section class="step optional"><div class="number">03 / НЕОБЯЗАТЕЛЬНЫЙ ПЕРЕНОС</div><h2>Перенесите выбранные диалоги в Codex</h2><p>Экспериментальный импортёр: проверьте план и изолированную пробу, затем перенесите и сверьте диалоги. Рабочие папки откройте в Codex самостоятельно.</p></section></div>'
                   '<p class="note">В других диалогах есть чек-лист, текст вложения и объяснение ограничений экспорта. Этот артефакт и все диалоги в демо вымышлены.</p></body></html>')
        z.writestr("artifacts/" + page["id"] + "/page.md",
                   "# Чек-лист архива и переноса\n\n"
                   "## Получить экспорт Claude\n\n1. На компьютере откройте Claude → Settings → Privacy → Export data.\n2. Дождитесь письма и откройте ссылку, войдя в свой аккаунт Claude.\n3. Если скачался manifest-….json, скачайте все архивы из его списка data_files. В примере четыре файла: conversations-000.zip, projects-000.zip, frames-000.zip и light_metadata-000.zip. Количество файлов в вашей выгрузке может отличаться.\n4. Сохраните все ZIP в одной личной папке вне публичного репозитория.\n\nJSON manifest — только список, не сами данные. У каждого элемента data_files есть filename и export_url.\n\n"
                   "**Запрос агенту:** «Прочитай этот manifest JSON и скачай все файлы из data_files по export_url в папку /путь/к/экспорту, сохранив имена filename. Проверь количество файлов и целостность ZIP. Уже скачанные исправные файлы повторно не скачивай». Агенту нужен доступ к локальным файлам и сети; если требуется вход в Claude через браузер, скачайте файлы по ссылкам вручную.\n\nСсылки действуют ограниченное время и могут перестать работать после использования. По официальной инструкции ссылка на экспорт действует 24 часа; скачивайте данные сразу. [Инструкция Claude](https://support.claude.com/en/articles/9450526-export-your-claude-data).\n\n"
                   "## Сохранить локальный архив\n\n1. Скачайте проект и откройте его папку в локальном ИИ-агенте. Нужен Python 3.9+.\n2. Попросите агента прочитать AGENTS.md и использовать claude-archive для личной папки с ZIP.\n3. Проверьте количество записей, недоступные версии и диалоги без проекта.\n4. Уточните состав проектов либо сохраните все диалоги и распределите их позже.\n5. Соберите архив и откройте локальный просмотрщик. Исходные ZIP сохраните отдельно.\n\nВ локальном архиве назначения записываются в organization.json и доступны другому браузеру и импортёру. В демо на сайте они сохраняются только в браузере посетителя.\n\n"
                   "## Если сохранились сведения о проектах\n\nПередайте агенту скриншоты, скопированную левую панель или свои заметки. Агент сопоставит их с экспортом, сохранит источник подтверждённых назначений и отдельно покажет спорные совпадения. Отсутствие чата на неполном скриншоте не означает, что он не относится к проекту.\n\n"
                   "## Пример сохранённой панели\n\nЭто вымышленный текст для демонстрации:\n\n```text\nClaude Archive · Начните здесь\n  01 · Что такое Claude Archive?\n  02 · Как получить и сохранить экспорт?\n```\n\nУ первого диалога в исходном экспорте нет назначения проекта: оно восстановлено по этой панели и сохранено отдельно с основанием. У второго назначение уже есть в экспорте. Разверните «Основание назначения» под выбором проекта в первом диалоге.\n\n"
                   "## При желании перенести диалоги в Codex\n\nИмпортёр экспериментальный; нужен совместимый Codex CLI. Переносятся видимые тексты сообщений. Инструменты, размышления и служебные инструкции не выполняются. Проекты боковой панели автоматически не создаются.\n\n1. Выберите нужные проекты или отдельные диалоги.\n2. Уточните спорные связи, которые могут изменить подборку.\n3. Попросите агента использовать claude-to-codex и показать план.\n4. Выполните пробный импорт в изолированную историю и проверьте сверку.\n5. Перенесите проверенную подборку с вашим разрешением. Ответ модели при импорте не запускается.\n6. Проверьте сверку и откройте рабочие папки с контекстом проектов и артефактами в Codex.\n7. При повторных запусках используйте ту же папку переноса и журнал: это помогает избежать дубликатов.\n\n"
                   "## Об этом демо\n\nВсе записи вымышлены. GitHub Pages показывает статическое демо; личные архивы и настоящий перенос остаются на вашем компьютере.\n")
    # Fictional evidence shown in the checklist above; no private source is used.
    key = "chats/" + ident("layout")
    org = {"projects": {key: project["uuid"]}, "frames": {}, "project_evidence": {key: {
        "project": project["uuid"], "source": "copied_sidebar", "status": "confirmed",
        "reference": "Чек-лист архива и переноса · раздел «Пример сохранённой панели»",
        "reason": "Вымышленный пример: полное название диалога указано под проектом и однозначно совпадает с записью экспорта."
    }}}
    (output / "organization.json").write_text(json.dumps(org, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(make_demo(parser.parse_args().output))
