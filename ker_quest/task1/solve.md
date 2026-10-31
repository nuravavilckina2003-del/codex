# «Уроки» — writeup

Задание: *«Заведите урок, приложите файл — и ждите звонка.»*
Флаг: `ctfcup{...}` (в материалах `uroki.zip` лежит только заглушка `ctfcup{test_flag}` из `Dockerfile`,
поэтому против живого инстанса нужно запускать `exploit.py http://HOST:PORT`).

## Что в задании

Flask-приложение «журнал уроков» + Celery beat в том же контейнере, supervisord, `/data` — единственный
каталог, куда пишет пользователь `app`. Флаг лежит в `/flag.txt` (`root:root`, 0644).

## Уязвимости

1. `app/storage.py`

```python
UNSAFE = re.compile(r"\.\.|\\|[\x00-\x1f]")

def clean_name(name):
    name = (name or "").strip()
    if UNSAFE.search(name):
        name = os.path.basename(name.replace("\\", "/"))
    ...
def save_attachment(folder, file):
    path = os.path.join(folder, clean_name(file.filename))
    file.save(path)
    return path
```

   Фильтр вырезает только `..`, `\` и управляющие символы, но **не** абсолютные пути.
   `os.path.join("/data/uploads", "/data/uroki.db")` возвращает `/data/uroki.db`,
   а `os.path.join("/data/uploads", "/flag.txt")` — `/flag.txt`.
   То есть имя файла в multipart-запросе задаёт произвольный путь записи, доступный пользователю `app`.

2. `app/web.py`, `download_attachment`

```python
return send_file(lesson["file_path"], as_attachment=True, download_name=lesson["file_name"])
```

   Путь берётся из БД и никак не проверяется — произвольное чтение файла, если в БД окажется
   нужный `file_path`.

## Эксплуатация

Прямая запись в `/flag.txt` не проходит: файл принадлежит `root`, а веб-процесс работает под `app`.
Зато `/data` целиком принадлежит `app`, включая саму базу `/data/uroki.db`.

1. `POST /lesson` — обычный урок, получаем `id` (в обработчике загрузки он всё равно нужен живым).
2. Готовим свою SQLite-базу со схемой приложения и двумя строками:
   * `id = lid` → `file_path = /data/uroki.db` (цель перезаписи),
   * `id = lid+1` → `file_path = /flag.txt` (то, что хотим прочитать).
3. `POST /lesson/<lid>/upload` с именем файла `/data/uroki.db`. `clean_name` пропускает абсолютный
   путь, `os.path.join` его сохраняет → база заменяется нашей. Следующий `INSERT/UPDATE`
   (`db.set_attachment`) затрагивает только строку `lid`, строка `lid+1` остаётся нетронутой.
4. `GET /lesson/<lid+1>/file` → `send_file("/flag.txt")` → флаг.

Скрипт: `exploit.py`.

## Проверка

Цепочка проверена на реальном коде из архива (Flask 3.0.3, Python 3.12-совместимо), поднятом
локально с заглушкой из Dockerfile:

```
[*] lesson id = 1
[*] upload -> 303
[*] download -> 200
ctfcup{test_flag}

[+] FLAG: ctfcup{test_flag}
```

## Почему «ждите звонка»

`ops.apply_schedule_changes()` вызывает `supervisorctl restart celery` при каждом изменении расписания —
это и есть «звонок». Для самой цепочки он не обязателен, но именно так задание подсказывает, что рядом
крутится Celery beat, а `/data` — общий и записываемый каталог (`/data/mq`, `/data/uroki.db`,
`celerybeat-schedule`).

## Как чинить

* `secure_filename` (werkzeug) + жёсткая проверка, что итоговый путь остаётся внутри `/data/uploads`
  (`os.path.realpath(path).startswith(os.path.realpath(folder) + os.sep)`).
* Хранить вложения под сгенерированным именем (uuid) и отдавать их только по id записи,
  а не по произвольному пути из БД.
* `/data` — не место для кода конфигурации и БД, доступной на запись веб-процессу без WAL/права
  только на свой каталог.
