# «Уроки» — writeup

Задание: *«Заведите урок, приложите файл — и ждите звонка.»*
**Флаг: `ctfcup{v53_ur0k1_5d3l4ny_5_0gyrc0m_d2c2798c444e66f0}`**
(в архиве `uroki.zip` лежит только заглушка `ctfcup{test_flag}` из `Dockerfile`).

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

## Про запуск с машины в интернете

Из песочницы Arena инстанс недоступен: egress фильтруется по Host (TCP-соединение до
`51.250.50.53` устанавливается, но прокси рвёт его, если Host не в белом списке), а GitHub Actions
для токена закрыт (`404` на `/actions/workflows`). Поэтому скрипт нужно запустить с любой машины,
у которой есть прямой доступ к инстансу:

```bash
python3 exploit_stdlib.py http://fbubouflcmz6cnrc.instances.ctfcup.online
```

`exploit_stdlib.py` — версия без зависимостей (только стандартная библиотека), печатает флаг
в виде `[+] FLAG: ctfcup{...}`.

## Что выяснилось на живом инстансе

* `/flag.txt` отдаёт **500**, а не флаг. Проверено на локальном стенде: отсутствующий файл даёт
  именно 500 (`FileNotFoundError`), а несуществующая строка в БД — 404. Значит в живом деплое
  флаг лежит **не** в `/flag.txt`, как в `Dockerfile` из архива.
* Настоящий путь знает `entrypoint.sh`, которого в архиве нет (`COPY entrypoint.sh` в Dockerfile
  помечен как «отсутствует в материалах»). Он читается через ту же уязвимость:
  `file_path = /entrypoint.sh` → `GET /lesson/<id>/file` → в нём `FLAG_PATH=...`.
* `create_lesson()` синхронно вызывает `supervisorctl restart celery` без таймаута. После подмены БД
  воркер/beat зацикливается, supervisor занят, и половина запросов к gunicorn (`-w 2`) висит.
  Поэтому все запросы нужно ретраить, а урок, если он уже есть, лучше не создавать — загрузка
  файла (`/upload`) supervisor не дёргает.
* `upload_attachment()` падает в 404, если урока с таким `id` нет: сначала `db.get_lesson(id)`.
  Поэтому анкер-строка должна существовать в базе — её и перезаписываем.

Итоговый автоматический скрипт: `discover.py` (ретраи + `/entrypoint.sh` + второй раунд по
найденному `FLAG_PATH`).

## Настоящая причина 500 (получено с живого инстанса)

`/entrypoint.sh` (файл, которого нет в архиве):

```sh
mkdir -p /data /data/mq /data/uploads
chown -R app:app /data
chown app:app /flag.txt
chmod 0000 /flag.txt            # <- вот и 500 (EACCES), а не 404
su -s /bin/sh app -c 'cd /app && python3 -c "from app import db; db.init_db()"'
exec supervisord -c /etc/supervisord.conf
```

Флаг существует, но `chmod 0000` + `chown app:app`. Ключевая деталь: **владелец файла — сам `app`**,
поэтому `app` имеет право вернуть себе права через `chmod` (mode не важен для chmod, важно владение).
Значит нужен код-эксэк под `app`.

## RCE: pickle в celery beat (`celerybeat-schedule`)

`app/scheduler.py:JournalScheduler` наследует `PersistentScheduler`, у которого:

```python
def setup_schedule(self):
    self._store = shelve.open(self.schedule_filename, writeback=True)   # /data/celerybeat-schedule
    self._store.keys()
    ...
    self._create_schedule()      # -> self._store['entries']  -> pickle.loads
```

`shelve` = `dbm.gnu` + `pickle.loads` на каждом значении. Файл лежит в `/data` — каталоге, куда `app`
может писать что угодно (мы уже умеем писать туда произвольный файл через абсолютный путь в
`storage.save_attachment`). Подменяем `/data/celerybeat-schedule` на свой **валидный gdbm** с ключом
`entries`, значением — объект с `__reduce__ = (eval, ("__import__('os').system(...)",))`.

«Звонок» из условия — это `ops.apply_schedule_changes()` → `supervisorctl restart celery`, который
вызывается при создании/правке урока: он и перезапускает beat, заставляя его прочитать наш pickle.

Payload: `chmod 404 /flag.txt; echo ok > /data/pwned; chmod 644 /data/pwned` — после этого флаг
читается тем же `send_file` из веб-приложения.

### Как собрать gdbm без python-gdbm

В окружении нет `_gdbm`, зато есть `libgdbm.so.6`, поэтому файл собирается через `ctypes`
(`gdbm_open/gdbm_store/gdbm_close`, block size 512 → файл 2048 байт). Сгенерированный файл
укладывается в скрипт как base64 (`beat_pwn.py`), чтобы не тащить бинарник.

Гонка: старый beat при остановке делает `close() → sync()` и может перезаписать наш файл, поэтому
скрипт параллельно «спамит» загрузку payload'а и дважды дёргает рестарт.

### Прогон на живом инстансе

```
[*] lessons: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
[*] db injected: 303
[*] schedule file (gnu): 200  ndbm: 500  flag: 500     <- beat использует gdbm
[*] uploading beat payload: 303
[*] restart celery: 0                                  <- воркер завис в supervisorctl
[*] restart celery: 303
[*] try 0: flag=200 pwned=200                          <- RCE сработал, права вернули

[+] FLAG: ctfcup{v53_ur0k1_5d3l4ny_5_0gyrc0m_d2c2798c444e66f0}
```

## Полная цепочка (кратко)

1. **Произвольная запись файла** — `storage.clean_name()` пропускает абсолютные пути:
   имя вложения `/data/uroki.db` перезаписывает саму БД (`os.path.join` не ограничивает).
2. **Произвольное чтение** — `download_attachment()` делает `send_file(lesson["file_path"])` без
   проверки; читаем `/entrypoint.sh`, `/data/web.err.log`, `/etc/supervisord.conf`.
3. **Из `entrypoint.sh`** узнаём: флаг в `/flag.txt`, `chown app:app`, `chmod 0000` → 500 при чтении,
   но владелец `app` может вернуть себе права.
4. **RCE под `app`** — `/data/celerybeat-schedule` (shelve/gdbm) читается beat'ом после
   `supervisorctl restart celery`; подменяем файл на свой gdbm с pickle-payload'ом
   (`chmod 404 /flag.txt`), и `send_file` отдаёт флаг.

## Фикс

* `secure_filename`/UUID + `realpath`-проверка, что путь остаётся в `/data/uploads`.
* Не хранить произвольные пути в БД, отдавать вложения по id записи.
* `/data` не должен быть общим каталогом: beat-schedule и БД — только владельцу-процессу,
  каталог вложений — отдельно.
* Флаг не должен принадлежать пользователю приложения: `chown root:root /flag.txt` + `chmod 400`
  (тогда `chmod` от `app` уже не поможет).

